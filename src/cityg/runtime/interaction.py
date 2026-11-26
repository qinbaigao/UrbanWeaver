"""Deterministic state-machine runtime for simulator-neutral interactions."""

from __future__ import annotations

import math
from dataclasses import dataclass

from cityg.geometry.model import GeometryScene, InteractionStateMachine, StateTransition
from cityg.validation import ValidationReport


@dataclass
class ActiveTransition:
    transition: StateTransition
    elapsed_s: float = 0.0


class InteractionRuntime:
    def __init__(self, machines: list[InteractionStateMachine]) -> None:
        self.machines = {machine.id: machine for machine in machines}
        self.current_states = {
            machine.id: machine.initial_state for machine in machines
        }
        self.active: dict[str, ActiveTransition] = {}

    def trigger(self, machine_id: str, action: str) -> None:
        machine = self.machines[machine_id]
        if machine_id in self.active:
            raise ValueError(f"State machine is already transitioning: {machine_id}")
        current = self.current_states[machine_id]
        transition = next(
            (
                item
                for item in machine.transitions
                if item.action == action and item.from_state == current
            ),
            None,
        )
        if transition is None:
            raise ValueError(f"Action {action!r} is invalid from state {current!r}")
        self.active[machine_id] = ActiveTransition(transition)

    def step(self, dt_s: float) -> None:
        if dt_s <= 0 or not math.isfinite(dt_s):
            raise ValueError("dt_s must be finite and positive")
        completed = []
        for machine_id, active in self.active.items():
            active.elapsed_s += dt_s
            if active.elapsed_s + 1e-9 >= active.transition.duration_s:
                self.current_states[machine_id] = active.transition.to_state
                completed.append(machine_id)
        for machine_id in completed:
            del self.active[machine_id]

    def value(self, machine_id: str, key: str):
        machine = self.machines[machine_id]
        active = self.active.get(machine_id)
        if active is None:
            return machine.states[self.current_states[machine_id]].get(key)
        start = machine.states[active.transition.from_state].get(key)
        end = machine.states[active.transition.to_state].get(key)
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            alpha = min(1.0, active.elapsed_s / active.transition.duration_s)
            return float(start) + (float(end) - float(start)) * alpha
        return start

    def snapshot(self) -> dict:
        if self.active:
            raise ValueError("Cannot snapshot while transitions are active")
        return {"states": dict(self.current_states)}

    def restore(self, snapshot: dict) -> None:
        states = snapshot.get("states", {})
        if set(states) != set(self.machines):
            raise ValueError("Snapshot state machine set does not match runtime")
        for machine_id, state in states.items():
            if state not in self.machines[machine_id].states:
                raise ValueError(f"Snapshot contains invalid state: {machine_id}={state}")
        self.current_states = dict(states)
        self.active.clear()


def run_interaction_smoke(
    scene: GeometryScene, *, dt_s: float = 0.1
) -> ValidationReport:
    """Exercise door and elevator controllers through bounded round trips."""

    report = ValidationReport()
    runtime = InteractionRuntime(scene.state_machines)
    transition_steps = 0
    door_ids = [
        machine.id
        for machine in scene.state_machines
        if machine.state_type == "revolute_door"
    ]
    elevator_ids = [
        machine.id
        for machine in scene.state_machines
        if machine.state_type == "elevator_controller"
    ]
    for action, expected_state in (("open", "open"), ("close", "closed")):
        for machine_id in door_ids:
            runtime.trigger(machine_id, action)
        while runtime.active:
            runtime.step(dt_s)
            transition_steps += 1
            for machine_id in door_ids:
                angle = runtime.value(machine_id, "joint_angle_deg")
                if angle is not None and (not math.isfinite(angle) or not 0 <= angle <= 90):
                    report.add(
                        "error",
                        "interaction_joint_limit",
                        "Door angle left its declared safe range",
                        machine_id,
                    )
        if any(runtime.current_states[item] != expected_state for item in door_ids):
            report.add(
                "error",
                "interaction_terminal_state",
                f"Not every state machine reached {expected_state}",
                scene.city_id,
            )
        snapshot = runtime.snapshot()
        restored = InteractionRuntime(scene.state_machines)
        restored.restore(snapshot)
        if restored.current_states != runtime.current_states:
            report.add(
                "error",
                "interaction_persistence",
                "State snapshot did not survive restore",
                scene.city_id,
            )
    for machine_id in elevator_ids:
        machine = runtime.machines[machine_id]
        levels = sorted(
            machine.states,
            key=lambda state: int(machine.states[state]["current_level"]),
        )
        if len(levels) < 2:
            report.add(
                "error",
                "interaction_elevator_levels",
                "Elevator controller must serve at least two levels",
                machine_id,
            )
            continue
        for target in (levels[-1], levels[0]):
            runtime.trigger(machine_id, f"go_to_{target}")
            while machine_id in runtime.active:
                runtime.step(dt_s)
                transition_steps += 1
                cabin_z = runtime.value(machine_id, "cabin_z_m")
                level_z = [
                    float(state["cabin_z_m"]) for state in machine.states.values()
                ]
                if cabin_z is None or not math.isfinite(cabin_z) or not min(level_z) <= cabin_z <= max(level_z):
                    report.add(
                        "error",
                        "interaction_elevator_limit",
                        "Elevator cabin left its declared vertical travel range",
                        machine_id,
                    )
            if runtime.current_states[machine_id] != target:
                report.add(
                    "error",
                    "interaction_elevator_terminal_state",
                    f"Elevator did not reach {target}",
                    machine_id,
                )
        snapshot = runtime.snapshot()
        restored = InteractionRuntime(scene.state_machines)
        restored.restore(snapshot)
        if restored.current_states != runtime.current_states:
            report.add(
                "error",
                "interaction_persistence",
                "State snapshot did not survive restore",
                scene.city_id,
            )
    report.metrics = {
        "state_machine_count": len(scene.state_machines),
        "door_controller_count": len(door_ids),
        "elevator_controller_count": len(elevator_ids),
        "transition_cycles": 2,
        "integration_steps": transition_steps,
        "dt_s": dt_s,
        "structural_physics_errors": len(report.errors),
        "runtime_kind": "deterministic_kinematic_smoke",
    }
    return report
