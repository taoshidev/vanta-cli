"""Subaccount creation command."""
import getpass
import json
import typer
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from bittensor_wallet import Wallet
from bittensor_cli.src.bittensor.utils import console

from vanta_cli.src.config import VANTA_API_BASE_URL_MAINNET, VANTA_API_BASE_URL_TESTNET
from vanta_cli.src.utils.api import make_api_request

async def create_subaccount(
    wallet: Wallet,
    network: str,
    account_size: float,
    asset_class: str,
    prompt: bool,
    quiet: bool = False,
    verbose: bool = False,
    json_output: bool = False
):
    """
    Create a new subaccount for an entity on the Vanta Network.

    This command:
    1. Fetches entity configuration (cost per theta, max account size)
    2. Validates account size and asset class
    3. Calculates required collateral
    4. Checks miner's collateral balance
    5. Prompts for deposit if insufficient collateral
    6. Creates subaccount with signature-based authentication
    """
    # Display header
    if not json_output:
        title = Text("🔗 VANTA NETWORK 🔗", style="bold blue")
        subtitle = Text("Subaccount Creation", style="italic cyan")
        panel = Panel.fit(
            f"{title}\n{subtitle}",
            style="bold blue",
            border_style="bright_blue"
        )
        console.print(panel)
        console.print("[blue]Creating subaccount on Vanta Network[/blue]")

    # Determine base URL
    base_url = VANTA_API_BASE_URL_TESTNET if network == "test" else VANTA_API_BASE_URL_MAINNET

    max_account_size = 100_000
    cost_per_theta = 5000

    # Step 2: Validate account size
    if account_size > max_account_size:
        console.print(f"[red]Account size ${account_size:,.0f} exceeds maximum ${max_account_size:,.0f}[/red]")
        return False

    if account_size <= 0:
        console.print("[red]Account size must be positive[/red]")
        return False

    # Step 3: Calculate required collateral
    required_theta = account_size / cost_per_theta

    # Display configuration
    if not json_output:
        config_table = Table(title="Subaccount Creation Configuration", show_header=True, header_style="bold cyan")
        config_table.add_column("Parameter", style="cyan")
        config_table.add_column("Value", style="green")

        config_table.add_row("Network", "Testnet" if network == "test" else "Mainnet")
        config_table.add_row("Account Size", f"${account_size:,.2f}")
        config_table.add_row("Asset Class", asset_class)
        config_table.add_row("Cost per Theta", f"${cost_per_theta:,.0f}")
        config_table.add_row("Required Collateral", f"{required_theta:.4f} Theta")

        console.print(config_table)

    # Step 4: Get password
    password = getpass.getpass(prompt='Enter your wallet password: ')

    try:
        coldkey = wallet.get_coldkey(password=password)
        hotkey = wallet.hotkey
    except Exception as e:
        console.print(f"[red]Failed to unlock wallet: {e}[/red]")
        return False

    # Step 5: Confirm creation
    if prompt:
        confirm = typer.confirm(
            f"Create subaccount for entity {hotkey.ss58_address} with "
            f"${account_size:,.2f} account size and {asset_class} asset class "
            f"(costs {required_theta:.4f} Theta)?"
        )
        if not confirm:
            console.print("[yellow]Subaccount creation cancelled[/yellow]")
            return False

    # Step 6: Ensure sufficient collateral
    response = make_api_request(f"/collateral/balance/{hotkey.ss58_address}", method="GET", base_url=base_url, dev_mode=verbose)
    if not response or response.get("balance_theta") < required_theta:
        console.print(f"[red]Insufficient collateral for subaccount creation: {response.get('balance_theta')}[/red]")
        return False

    # Step 7: Prepare and sign subaccount creation request
    console.print("\n[cyan]Signing subaccount creation request...[/cyan]")

    subaccount_data = {
        "entity_coldkey": coldkey.ss58_address,
        "entity_hotkey": hotkey.ss58_address,
        "account_size": account_size,
        "asset_class": asset_class
    }

    # Create message to sign (sorted JSON)
    message = json.dumps(subaccount_data, sort_keys=True)

    # Sign the message with coldkey
    signature = coldkey.sign(message.encode('utf-8')).hex()

    # Prepare payload
    payload = {
        "entity_coldkey": coldkey.ss58_address,
        "entity_hotkey": hotkey.ss58_address,
        "account_size": account_size,
        "asset_class": asset_class,
        "signature": signature
    }

    # Step 8: Send subaccount creation request
    console.print("\n[cyan]Sending subaccount creation request...[/cyan]")

    try:
        response = make_api_request("/entity/create-subaccount", payload, base_url=base_url, dev_mode=verbose)

        if response is None:
            console.print("[red]Subaccount creation failed - no response[/red]")
            return False

        # Check success
        if response.get("status") == "success":
            console.print(f"[green]{response.get('message')}[/green]")

            subaccount = response.get('subaccount', {})

            # Display success info
            success_table = Table(title="Subaccount Created Successfully", show_header=True, header_style="bold green")
            success_table.add_column("Field", style="cyan")
            success_table.add_column("Value", style="green")

            success_table.add_row("Synthetic Hotkey", subaccount.get('synthetic_hotkey'))
            success_table.add_row("Subaccount ID", str(subaccount.get('subaccount_id')))
            success_table.add_row("Subaccount UUID", subaccount.get('subaccount_uuid'))
            success_table.add_row("Account Size", f"${subaccount.get('account_size'):,.2f}")
            success_table.add_row("Asset Class", subaccount.get('asset_class'))
            success_table.add_row("Status", subaccount.get('status'))
            success_table.add_row("Collateral Charged", f"{required_theta:.4f} Theta")

            console.print(success_table)

            success_panel = Panel.fit(
                f"🎉 Subaccount created successfully!\n"
                f"Synthetic Hotkey: {subaccount.get('synthetic_hotkey')}\n"
                f"Use this hotkey to place orders and track performance.",
                style="bold green",
                border_style="green"
            )
            console.print(success_panel)
            return True
        else:
            error_message = response.get("error") or "Unknown error occurred"
            console.print(f"[red]Subaccount creation failed: {error_message}[/red]")
            return False

    except Exception as e:
        console.print(f"[red]Error during subaccount creation: {e}[/red]")
        return False
