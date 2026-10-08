"""Shared linear repeater workload on actual SimQN or NetSquid event engines.

Same-time repeater measurements run in index order within a callback. This
keeps the state local (at most 4 qubits) while adding no protocol-time delay.
"""

import time
from functools import partial

from qns.simulator.event import Event
from qns.simulator.simulator import Simulator

from evaluations.fig6_backends import make_backend

TICKS = 1_000_000_000


class CallbackEvent(Event):
    def __init__(self, when, callback, order):
        super().__init__(t=when)
        self.callback, self.order = callback, order

    def invoke(self):
        self.callback()

    def __lt__(self, other):
        return (self.t.time_slot, self.order) < (other.t.time_slot, other.order)


class SimQNScheduler:
    def __init__(self, end):
        self.sim = Simulator(0, end / TICKS, accuracy=TICKS)
        # qns converts seconds to slots by truncation. Reapply the exact bound
        # so e.g. 1005 ns cannot become 1004 ns through float multiplication.
        self.sim.te = self.sim.time(time_slot=end)
        self.sim.event_pool.te = self.sim.te
        self.order = 0
        self.event_count = 0
        self.end = end

    def schedule(self, tick, callback):
        if tick <= self.end:
            self.order += 1
            self.sim.add_event(
                CallbackEvent(
                    self.sim.time(time_slot=tick),
                    partial(self.invoke, callback),
                    self.order,
                )
            )

    def invoke(self, callback):
        self.event_count += 1
        callback()

    def run(self):
        self.sim.run()


class NetSquidScheduler:
    def __init__(self, end):
        import netsquid as ns
        from pydynaa import Entity, EventHandler, EventType

        ns.sim_reset()
        self.ns, self.end = ns, end
        self.event_count = 0
        self.callbacks = {}
        self.entity = type("Fig6Entity", (Entity,), {})()
        self.kind = EventType("FIG6_CALLBACK", "Shared repeater workload event")
        self.handler = EventHandler(self.invoke)
        self.entity._wait(self.handler, entity=self.entity, event_type=self.kind)

    def schedule(self, tick, callback):
        if tick <= self.end:
            event = self.entity._schedule_at(float(tick), self.kind)
            self.callbacks[event] = callback

    def invoke(self, event):
        self.event_count += 1
        self.callbacks.pop(event)()

    def run(self):
        # NetSquid end_time is exclusive; include events exactly on the boundary.
        try:
            self.ns.sim_run(end_time=self.end + 1)
        finally:
            self.entity._dismiss(self.handler, entity=self.entity, event_type=self.kind)
            self.callbacks.clear()


def run_trial(backend: str, nodes: int, settings: dict, seed: int) -> dict:
    start = time.perf_counter_ns()
    end = round(settings["duration"] * TICKS)
    hop = round(settings["link_length_km"] / settings["speed_km_s"] * TICKS)
    scheduler = NetSquidScheduler(end) if backend == "netsquid" else SimQNScheduler(end)
    model = make_backend(backend, settings, seed)
    completions, fidelities, rounds = [], [], []
    scheduled_rounds = 0

    def finish(round_id, pair, tick, x=0, z=0):
        model.apply_noise(pair, tick / TICKS)
        model.correct(pair, x, z)
        completions.append(tick / TICKS)
        fidelities.append(model.fidelity(pair))
        rounds.append(round_id)

    def generate(round_id, tick):
        pairs = [model.create_link(tick / TICKS, hop / TICKS) for _ in range(nodes - 1)]
        arrivals = [0]
        ready = tick + hop

        def arrived():
            arrivals[0] += 1
            if arrivals[0] != nodes - 1:
                return
            if nodes == 2:
                finish(round_id, pairs[0], ready)
            else:
                scheduler.schedule(ready, swapping)

        def swapping():
            pair = pairs[0]
            messages = []
            for index, right in enumerate(pairs[1:], start=1):
                pair, x, z = model.swap(pair, right, ready / TICKS)
                messages.append((ready + (nodes - 1 - index) * hop, x, z))
            parity = [0, 0, 0]

            def notified(tick, x, z):
                parity[0] ^= x
                parity[1] ^= z
                parity[2] += 1
                if parity[2] == nodes - 2:
                    finish(round_id, pair, tick, parity[0], parity[1])

            for message_tick, x, z in messages:
                scheduler.schedule(message_tick, partial(notified, message_tick, x, z))

        for _ in pairs:
            scheduler.schedule(ready, arrived)

    # Round indices prevent accumulated floating-point period drift.
    while True:
        tick = round(scheduled_rounds / settings["send_rate"] * TICKS)
        if tick >= end:
            break
        scheduler.schedule(tick, partial(generate, scheduled_rounds, tick))
        scheduled_rounds += 1
    setup_end = time.perf_counter_ns()
    scheduler.run()
    stop = time.perf_counter_ns()
    return {
        "completed_pairs": len(rounds),
        "completed_rounds": rounds,
        "completion_times": completions,
        "completion_fidelities": fidelities,
        "scheduled_rounds": scheduled_rounds,
        "event_count": scheduler.event_count,
        "max_state_qubits": model.max_state_qubits,
        "setup_seconds": (setup_end - start) / 1e9,
        "simulation_seconds": (stop - setup_end) / 1e9,
        "job_seconds": (stop - start) / 1e9,
    }
