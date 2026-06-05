from collections import defaultdict, deque

from app.schemas.workflow import Edge, Node


def validate_dag(nodes: list[Node], edges: list[Edge]) -> None:
    node_ids = [node.id for node in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("Duplicate node IDs are not allowed")

    node_set = set(node_ids)
    for edge in edges:
        if edge.from_ not in node_set:
            raise ValueError(f"Edge references unknown source node: {edge.from_}")
        if edge.to not in node_set:
            raise ValueError(f"Edge references unknown target node: {edge.to}")

    in_degree: dict[str, int] = {node_id: 0 for node_id in node_ids}
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        adjacency[edge.from_].append(edge.to)
        in_degree[edge.to] += 1

    queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for neighbor in adjacency[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited != len(node_ids):
        raise ValueError("Workflow contains a cycle")


def get_entry_nodes(nodes: list[Node], edges: list[Edge]) -> list[str]:
    has_incoming = {edge.to for edge in edges}
    return [node.id for node in nodes if node.id not in has_incoming]


def get_parent_map(edges: list[Edge]) -> dict[str, list[str]]:
    parents: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        parents[edge.to].append(edge.from_)
    return parents


def get_children_map(edges: list[Edge]) -> dict[str, list[str]]:
    children: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        children[edge.from_].append(edge.to)
    return children


def get_ready_nodes(
    node_ids: list[str],
    edges: list[Edge],
    completed: set[str],
) -> list[str]:
    parents = get_parent_map(edges)
    ready: list[str] = []
    for node_id in node_ids:
        if node_id in completed:
            continue
        node_parents = parents.get(node_id, [])
        if not node_parents:
            continue
        if all(parent in completed for parent in node_parents):
            ready.append(node_id)
    return ready
