from __future__ import annotations

import unittest

from code2paper.agentic.graph import _route_functions
from code2paper.agentic.graph_catalog import build_graph_catalog
from code2paper.agentic.graph_routes import FROZEN_EVIDENCE_KEYS, VALIDATION_KEYS
from code2paper.agentic.graph_topology import (
    CONDITIONAL_ROUTE_SPECS,
    DIRECT_EDGE_SPECS,
    EVIDENCE_GATE_SPECS,
    STAGE_NODE_NAMES,
    TERMINAL_EDGE_SPECS,
)


class AgenticGraphTopologyTests(unittest.TestCase):
    def test_graph_catalog_and_runtime_routes_use_shared_topology_contract(self) -> None:
        catalog = build_graph_catalog()

        stage_nodes = [node.name for node in catalog.nodes if node.kind == "stage"]
        edge_pairs = {(edge.source, edge.target) for edge in catalog.edges}
        route_map = {route.source: route for route in catalog.conditional_routes}

        self.assertEqual(stage_nodes, list(STAGE_NODE_NAMES))
        self.assertTrue(all((edge.source, edge.target) in edge_pairs for edge in DIRECT_EDGE_SPECS))
        self.assertTrue(all((edge.source, edge.target) in edge_pairs for edge in TERMINAL_EDGE_SPECS))
        self.assertEqual(set(route_map), {route.source for route in CONDITIONAL_ROUTE_SPECS})
        self.assertTrue(all(route_map[route.source].routes == dict(route.routes) for route in CONDITIONAL_ROUTE_SPECS))
        self.assertEqual(set(_route_functions()), {route.router for route in CONDITIONAL_ROUTE_SPECS})

    def test_catalog_and_runtime_use_shared_evidence_gate_contract(self) -> None:
        catalog = build_graph_catalog()

        gate_map = {gate.name: gate for gate in catalog.evidence_gates}
        frozen_gate = next(gate for gate in EVIDENCE_GATE_SPECS if gate.name == "frozen_evidence_gate")
        validation_gate = next(gate for gate in EVIDENCE_GATE_SPECS if gate.name == "validation_gate")

        self.assertEqual(set(gate_map), {gate.name for gate in EVIDENCE_GATE_SPECS})
        self.assertTrue(
            all(gate_map[gate.name].required_artifacts == list(gate.required_artifacts) for gate in EVIDENCE_GATE_SPECS)
        )
        self.assertEqual(FROZEN_EVIDENCE_KEYS, set(frozen_gate.required_artifacts))
        self.assertEqual(VALIDATION_KEYS, set(validation_gate.required_artifacts))


if __name__ == "__main__":
    unittest.main()
