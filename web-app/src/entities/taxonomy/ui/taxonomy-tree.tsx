"use client";

import dagre from "@dagrejs/dagre";
import {
  Background,
  Controls,
  type Edge,
  Handle,
  MarkerType,
  MiniMap,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  type ReactFlowInstance,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import { useEffect, useState } from "react";

import type { TaxonomyTreeNode } from "@/entities/taxonomy/types/taxonomy";
import { Button } from "@/shared/ui/button";

export interface TaxonomyTreeProps {
  nodes: TaxonomyTreeNode[];
}

type GraphNodeData = Record<string, unknown> & {
  label: string;
  conceptId: string;
  score: number | null;
  depth: number;
};

const NODE_WIDTH = 300;
const NODE_HEIGHT = 98;

function ConceptNodeCard({ data }: NodeProps<Node<GraphNodeData>>) {
  return (
    <div className="min-w-[300px] rounded-[24px] border border-[color:var(--color-border)] bg-white/95 px-5 py-4 shadow-[0_14px_32px_rgba(17,17,17,0.08)]">
      <Handle className="!opacity-0" position={Position.Top} type="target" />
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="truncate text-lg font-semibold text-[color:var(--color-ink)]">
            {data.label}
          </p>
          <p className="mt-2 truncate text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-muted-soft)]">
            {data.conceptId}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-muted-soft)]">
            Score
          </p>
          <p className="mt-1 text-base font-medium text-[color:var(--color-ink)]">
            {data.score?.toFixed(2) ?? "n/a"}
          </p>
        </div>
      </div>
      <Handle className="!opacity-0" position={Position.Bottom} type="source" />
    </div>
  );
}

const nodeTypes = {
  concept: ConceptNodeCard,
};

function getTreeStats(node: TaxonomyTreeNode): { count: number; maxDepth: number } {
  if (node.children.length === 0) {
    return { count: 1, maxDepth: 1 };
  }

  let count = 1;
  let maxDepth = 1;

  for (const child of node.children) {
    const childStats = getTreeStats(child);
    count += childStats.count;
    maxDepth = Math.max(maxDepth, childStats.maxDepth + 1);
  }

  return { count, maxDepth };
}

function buildGraph(root: TaxonomyTreeNode, rootIndex: number) {
  const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  const flowNodes: Node<GraphNodeData>[] = [];
  const flowEdges: Edge[] = [];

  graph.setGraph({
    rankdir: "TB",
    ranksep: 110,
    nodesep: 42,
    marginx: 36,
    marginy: 36,
  });

  const walk = (
    node: TaxonomyTreeNode,
    depth: number,
    path: string,
    parentId: string | null,
  ) => {
    const id = `${path}-${node.conceptId}`;

    graph.setNode(id, { height: NODE_HEIGHT, width: NODE_WIDTH });

    flowNodes.push({
      id,
      type: "concept",
      draggable: true,
      position: { x: 0, y: 0 },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      style: { width: NODE_WIDTH },
      data: {
        conceptId: node.conceptId,
        depth,
        label: node.label,
        score: node.score,
      },
    });

    if (parentId) {
      graph.setEdge(parentId, id);
      flowEdges.push({
        id: `${parentId}-${id}`,
        source: parentId,
        target: id,
        type: "smoothstep",
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "rgba(17, 17, 17, 0.35)",
          width: 16,
          height: 16,
        },
        style: {
          stroke: "rgba(17, 17, 17, 0.2)",
          strokeWidth: 1.35,
        },
      });
    }

    node.children.forEach((child, index) => {
      walk(child, depth + 1, `${path}-${index}`, id);
    });
  };

  walk(root, 0, `root-${rootIndex}`, null);
  dagre.layout(graph);

  return {
    edges: flowEdges,
    nodes: flowNodes.map((node) => {
      const positionedNode = graph.node(node.id);

      return {
        ...node,
        position: {
          x: positionedNode.x - NODE_WIDTH / 2,
          y: positionedNode.y - NODE_HEIGHT / 2,
        },
      };
    }),
  };
}

export function TaxonomyTreeView({ nodes }: TaxonomyTreeProps) {
  const [selectedRootIndex, setSelectedRootIndex] = useState(0);
  const [flowInstance, setFlowInstance] =
    useState<ReactFlowInstance<Node<GraphNodeData>, Edge> | null>(null);
  const activeRootIndex =
    nodes[selectedRootIndex] !== undefined ? selectedRootIndex : 0;

  const activeRoot = nodes[Math.min(activeRootIndex, Math.max(nodes.length - 1, 0))];
  const initialGraph = activeRoot ? buildGraph(activeRoot, activeRootIndex) : { nodes: [], edges: [] };
  const [flowNodes, setFlowNodes, onNodesChange] =
    useNodesState<Node<GraphNodeData>>(initialGraph.nodes);
  const [flowEdges, setFlowEdges, onEdgesChange] = useEdgesState(initialGraph.edges);

  useEffect(() => {
    const nextRoot = nodes[activeRootIndex];
    if (!nextRoot) {
      setFlowNodes([]);
      setFlowEdges([]);
      return;
    }

    const nextGraph = buildGraph(nextRoot, activeRootIndex);
    setFlowNodes(nextGraph.nodes);
    setFlowEdges(nextGraph.edges);

    requestAnimationFrame(() => {
      flowInstance?.fitView({ maxZoom: 1.05, padding: 0.22 });
    });
  }, [activeRootIndex, flowInstance, nodes, setFlowEdges, setFlowNodes]);

  if (nodes.length === 0) {
    return (
      <div className="rounded-[28px] border border-dashed border-[color:var(--color-border-strong)] bg-[color:var(--color-surface-muted)] p-8 text-center">
        <h3 className="text-lg font-semibold text-[color:var(--color-ink)]">
          No root concepts available
        </h3>
        <p className="mt-2 text-sm leading-6 text-[color:var(--color-muted)]">
          The taxonomy tree exists but contains no root nodes yet.
        </p>
      </div>
    );
  }

  const activeStats = getTreeStats(activeRoot);

  return (
    <div className="overflow-hidden rounded-[28px] border border-[color:var(--color-border)] bg-[color:var(--color-surface-muted)]">
      <div className="space-y-4 border-b border-[color:var(--color-border)] px-5 py-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-[color:var(--color-muted-soft)]">
              Taxonomy graph
            </p>
            <p className="mt-1 text-sm text-[color:var(--color-muted)]">
              Focused branch view. Switch between root concepts, then drag nodes or pan the canvas.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
            <div className="rounded-[18px] border border-[color:var(--color-border)] bg-white/75 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-muted-soft)]">
                Roots
              </p>
              <p className="mt-1 font-semibold text-[color:var(--color-ink)]">{nodes.length}</p>
            </div>
            <div className="rounded-[18px] border border-[color:var(--color-border)] bg-white/75 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-muted-soft)]">
                Nodes
              </p>
              <p className="mt-1 font-semibold text-[color:var(--color-ink)]">{activeStats.count}</p>
            </div>
            <div className="rounded-[18px] border border-[color:var(--color-border)] bg-white/75 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--color-muted-soft)]">
                Depth
              </p>
              <p className="mt-1 font-semibold text-[color:var(--color-ink)]">
                {activeStats.maxDepth}
              </p>
            </div>
          </div>
        </div>

        {nodes.length > 1 ? (
          <div className="flex gap-2 overflow-x-auto pb-1">
            {nodes.map((rootNode, index) => (
              <Button
                className="shrink-0"
                key={`${rootNode.conceptId}-${index}`}
                onClick={() => setSelectedRootIndex(index)}
                variant={index === activeRootIndex ? "primary" : "secondary"}
              >
                {rootNode.label}
              </Button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="h-[760px] w-full">
        <ReactFlow<Node<GraphNodeData>, Edge>
          defaultEdgeOptions={{
            style: { stroke: "rgba(17, 17, 17, 0.2)", strokeWidth: 1.35 },
            type: "smoothstep",
          }}
          edges={flowEdges}
          fitView
          fitViewOptions={{ maxZoom: 1.05, padding: 0.22 }}
          minZoom={0.3}
          nodeTypes={nodeTypes}
          nodes={flowNodes}
          onEdgesChange={onEdgesChange}
          onInit={(instance) => setFlowInstance(instance)}
          onNodesChange={onNodesChange}
          panOnDrag
          proOptions={{ hideAttribution: true }}
          selectionOnDrag={false}
        >
          <Background color="rgba(17, 17, 17, 0.06)" gap={24} size={1.1} />
          <MiniMap
            maskColor="rgba(17, 17, 17, 0.06)"
            nodeColor={() => "rgba(17, 17, 17, 0.88)"}
            pannable
            position="bottom-right"
            style={{
              backgroundColor: "rgba(255, 255, 255, 0.96)",
              border: "1px solid rgba(17, 17, 17, 0.08)",
              height: 120,
              width: 180,
            }}
            zoomable
          />
          <Controls position="top-right" showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  );
}
