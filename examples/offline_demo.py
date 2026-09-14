"""Run with: python examples/offline_demo.py. No web service or CAD kernel required."""
from cad_integrity import RepairPipeline, RepairPolicy, WeldPolicy
from cad_integrity.fixtures import cracked_cube
from cad_integrity.serialization import dumps


def main() -> None:
    result = RepairPipeline(RepairPolicy(weld=WeldPolicy(tolerance=0.005, max_displacement=0.005))).run(
        cracked_cube(), on_event=lambda event: print(f"[{event.stage}] {event.message}")
    )
    print(dumps(result.report))


if __name__ == "__main__":
    main()
