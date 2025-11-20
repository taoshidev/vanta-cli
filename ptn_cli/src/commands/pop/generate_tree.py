from typing import Optional
import sys
import json
from pathlib import Path
from proof_of_portfolio.signal_processor import (
    generate_validator_trees,
    get_validator_tree_hashes,
)


async def generate_tree(
    signals_dir: Optional[str] = None,
    hotkey: Optional[str] = None,
    output_path: Optional[str] = None,
    quiet: bool = False,
    verbose: bool = False,
    json_output: bool = False,
):
    """
    Generate merkle trees for miners using processed signals from mining directory
    """

    if not signals_dir:
        current_dir = Path.cwd()
        potential_dirs = [
            current_dir / "mining" / "processed_signals",
            current_dir / "processed_signals",
            Path("./mining/processed_signals"),
        ]

        for dir_path in potential_dirs:
            if dir_path.exists() and dir_path.is_dir():
                signals_dir = str(dir_path)
                if not quiet:
                    print(f"Found signals directory: {signals_dir}")
                break

        if not signals_dir:
            if not quiet:
                print("Error: No processed signals directory found.", file=sys.stderr)
                print(
                    "Please provide --signals-dir path or place files in ./mining/processed_signals/",
                    file=sys.stderr,
                )
            return False

    signals_path = Path(signals_dir)
    if not signals_path.exists() or not signals_path.is_dir():
        if not quiet:
            print(
                f"Error: Signals directory not found at {signals_dir}", file=sys.stderr
            )
        return False

    try:
        validator_trees = generate_validator_trees(
            signals_dir=signals_dir, hotkey=hotkey, output_dir=output_path, quiet=quiet
        )

        if not validator_trees:
            return False

        validator_hashes = get_validator_tree_hashes(validator_trees)

        if json_output:
            result = {
                "validator_trees": len(validator_trees),
                "validators": {
                    validator_key: {
                        "order_count": data["order_count"],
                        "output_path": data["output_path"],
                        "tree_hash": data["tree_hash"],
                    }
                    for validator_key, data in validator_trees.items()
                },
            }
            print(json.dumps(result, indent=2))
        else:
            print("\nExpected Tree Hashes:")
            print("-" * 80)
            for validator_key, tree_hash in validator_hashes.items():
                data = validator_trees[validator_key]
                print(f"Validator: {validator_key}")
                print(f"Hash:      {tree_hash}")
                print(f"Orders:    {data['order_count']}")
                print(f"Output:    {data['output_path']}")
                print("-" * 80)

        return True

    except Exception as e:
        if not quiet:
            import traceback

            print(f"Error generating trees: {str(e)}", file=sys.stderr)
            if verbose:
                print(f"Full traceback:", file=sys.stderr)
                traceback.print_exc()
        return False
