<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import { useSessionStore } from '@/stores/session'
import type { LineageNode, LineageEdge } from '@/types'

const store = useSessionStore()
const svgRef = ref<SVGSVGElement | null>(null)

const WIDTH = 300
const NODE_RADIUS = 24

interface LayoutNode extends LineageNode {
  x: number
  y: number
}

function layoutNodes(nodes: LineageNode[], edges: LineageEdge[]): LayoutNode[] {
  if (nodes.length === 0) return []

  // Simple vertical layout: ancestors at top, descendants at bottom
  const layers: Map<string, number> = new Map()

  // Build adjacency
  const children = new Map<string, string[]>()
  const parents = new Map<string, string[]>()
  for (const e of edges) {
    if (!children.has(e.source)) children.set(e.source, [])
    children.get(e.source)!.push(e.target)
    if (!parents.has(e.target)) parents.set(e.target, [])
    parents.get(e.target)!.push(e.source)
  }

  // Assign layers via BFS from nodes with no parents (root nodes)
  const roots = nodes.filter((n) => !parents.has(n.id) || parents.get(n.id)!.length === 0)
  if (roots.length === 0) {
    // All connected, pick first as root
    return nodes.map((n, i) => ({
      ...n,
      x: 40 + (i % 2) * 200,
      y: 60 + Math.floor(i / 2) * 100,
    }))
  }

  const visited = new Set<string>()
  const queue = roots.map((r) => ({ id: r.id, layer: 0 }))
  for (const { id, layer } of queue) {
    if (visited.has(id)) continue
    visited.add(id)
    layers.set(id, Math.min(layer, layers.get(id) ?? Infinity))

    const kids = children.get(id) || []
    for (const kid of kids) {
      queue.push({ id: kid, layer: layer + 1 })
    }
  }

  // Place nodes in layers
  const layerGroups = new Map<number, string[]>()
  for (const [id, layer] of layers) {
    if (!layerGroups.has(layer)) layerGroups.set(layer, [])
    layerGroups.get(layer)!.push(id)
  }

  // Also place any unvisited nodes
  let maxLayer = layerGroups.size > 0 ? Math.max(...layerGroups.keys()) : 0
  for (const node of nodes) {
    if (!visited.has(node.id)) {
      maxLayer++
      if (!layerGroups.has(maxLayer)) layerGroups.set(maxLayer, [])
      layerGroups.get(maxLayer)!.push(node.id)
    }
  }

  const layout: LayoutNode[] = []
  for (const [layer, ids] of layerGroups) {
    const y = 60 + layer * 100
    const spacing = WIDTH / (ids.length + 1)
    ids.forEach((id, i) => {
      const node = nodes.find((n) => n.id === id)
      if (node) {
        layout.push({ ...node, x: spacing * (i + 1), y })
      }
    })
  }

  return layout
}

function drawGraph() {
  const svg = svgRef.value
  if (!svg) return

  const layered = layoutNodes(store.lineageNodes, store.lineageEdges)

  // Clear
  svg.innerHTML = ''

  if (layered.length === 0) {
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text')
    text.setAttribute('x', String(WIDTH / 2))
    text.setAttribute('y', '50')
    text.setAttribute('text-anchor', 'middle')
    text.setAttribute('fill', 'var(--color-text-muted)')
    text.setAttribute('font-size', '12')
    text.textContent = 'No lineage data'
    svg.appendChild(text)
    return
  }

  // Draw edges
  for (const edge of store.lineageEdges) {
    const source = layered.find((n) => n.id === edge.source)
    const target = layered.find((n) => n.id === edge.target)
    if (!source || !target) continue

    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line')
    line.setAttribute('x1', String(source.x))
    line.setAttribute('y1', String(source.y + NODE_RADIUS))
    line.setAttribute('x2', String(target.x))
    line.setAttribute('y2', String(target.y - NODE_RADIUS))
    line.setAttribute('stroke', 'var(--color-border)')
    line.setAttribute('stroke-width', '2')
    line.setAttribute('marker-end', 'url(#arrowhead)')

    // Label
    const mx = (source.x + target.x) / 2
    const my = (source.y + target.y) / 2
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text')
    text.setAttribute('x', String(mx))
    text.setAttribute('y', String(my - 4))
    text.setAttribute('text-anchor', 'middle')
    text.setAttribute('fill', 'var(--color-text-muted)')
    text.setAttribute('font-size', '10')
    text.textContent = edge.edge_type || '→'

    svg.appendChild(line)
    svg.appendChild(text)
  }

  // Draw arrow marker
  const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs')
  const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker')
  marker.setAttribute('id', 'arrowhead')
  marker.setAttribute('markerWidth', '8')
  marker.setAttribute('markerHeight', '6')
  marker.setAttribute('refX', '0')
  marker.setAttribute('refY', '3')
  marker.setAttribute('orient', 'auto')
  const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon')
  polygon.setAttribute('points', '0 0, 8 3, 0 6')
  polygon.setAttribute('fill', 'var(--color-border)')
  marker.appendChild(polygon)
  defs.appendChild(marker)
  svg.appendChild(defs)

  // Draw nodes
  for (const node of layered) {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g')

    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
    circle.setAttribute('cx', String(node.x))
    circle.setAttribute('cy', String(node.y))
    circle.setAttribute('r', String(NODE_RADIUS))
    circle.setAttribute('fill', node.type === 'dataset' ? 'var(--color-accent)' : 'var(--color-success)')
    circle.setAttribute('stroke', 'var(--color-bg-primary)')
    circle.setAttribute('stroke-width', '2')

    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text')
    text.setAttribute('x', String(node.x))
    text.setAttribute('y', String(node.y + 4))
    text.setAttribute('text-anchor', 'middle')
    text.setAttribute('fill', 'white')
    text.setAttribute('font-size', '9')
    text.setAttribute('font-weight', '600')
    text.textContent = node.name.length > 12 ? node.name.slice(0, 10) + '...' : node.name

    g.appendChild(circle)
    g.appendChild(text)
    svg.appendChild(g)
  }
}

const layoutedNodes = computed(() => layoutNodes(store.lineageNodes, store.lineageEdges))

// Initial draw + reactive updates
onMounted(() => {
  drawGraph()
})

watch(
  () => [store.lineageNodes.length, store.lineageEdges.length],
  () => {
    drawGraph()
  }
)
</script>

<template>
  <div class="lineage-graph">
    <h4 class="graph-title">Lineage Graph</h4>
    <svg ref="svgRef" :viewBox="`0 0 ${WIDTH} ${Math.max(200, layoutedNodes.length * 100 + 40)}`" class="graph-svg"></svg>
  </div>
</template>

<style scoped>
.lineage-graph {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.graph-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted);
}

.graph-svg {
  width: 100%;
  min-height: 200px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  background: var(--color-bg-primary);
}
</style>
