import dataclasses
import inspect
import os
from dataclasses import dataclass

import click
import meraki


@dataclass
class SwitchDevice:
    """Meraki switch device configuration."""

    name: str | None = None
    model: str | None = None
    mac: str | None = None
    tags: list[str] | None = None
    lat: float | None = None
    lng: float | None = None
    address: str | None = None
    notes: str | None = None
    floorPlanId: str | None = None


@dataclass
class SwitchPort:
    """Meraki switch port configuration."""

    portId: str | None = None
    name: str | None = None
    tags: list[str] | None = None
    enabled: bool | None = None
    poeEnabled: bool | None = None
    type: str | None = None
    vlan: int | None = None
    voiceVlan: int | None = None
    allowedVlans: str | None = None
    isolationEnabled: bool | None = None
    rstpEnabled: bool | None = None
    stpGuard: str | None = None
    linkNegotiation: str | None = None
    portScheduleId: str | None = None
    udld: str | None = None
    accessPolicyType: str | None = None
    accessPolicyNumber: int | None = None
    macAllowList: list[str] | None = None
    stickyMacAllowList: list[str] | None = None
    stickyMacAllowListLimit: int | None = None
    stormControlEnabled: bool | None = None
    adaptivePolicyGroupId: str | None = None
    peerSgtCapable: bool | None = None
    flexibleStackingEnabled: bool | None = None
    daiTrusted: bool | None = None
    profile: dict | None = None


def get_switch_config(dashboard_api, serial: str) -> SwitchDevice:
    """Get switch configuration.

    Parameters
    ----------
    dashboard_api : meraki.DashboardAPI
        Meraki Dashboard API object.
    serial : str
        Serial number of switch to get port configurations from.

    Returns
    -------
    switch_config : SwitchDevice
        Switch configuration.
    """
    try:
        response = dashboard_api.devices.getDevice(serial)
        switch_config = SwitchDevice(
            **{k: v for k, v in response.items() if k in inspect.signature(SwitchDevice).parameters}
        )
        return switch_config
    except Exception as e:
        raise click.ClickException(f'Error getting switch configuration for {serial}.') from e


def get_switch_ports(dashboard_api, serial: str) -> list[SwitchPort]:
    """Get configuration details for each port on a switch.

    Parameters
    ----------
    dashboard_api : meraki.DashboardAPI
        Meraki Dashboard API object.
    serial : str
        Serial number of switch to get port configurations from.

    Returns
    -------
    ports : list[SwitchPort]
        List of port configurations.
    """
    try:
        response = dashboard_api.switch.getDeviceSwitchPorts(serial)
        ports: list[SwitchPort] = []
        for port in response:
            ports.append(SwitchPort(**{k: v for k, v in port.items() if k in inspect.signature(SwitchPort).parameters}))

        if len(ports) == 0:
            raise click.ClickException(f'Response contained zero port configurations for switch {serial}.')

        return ports
    except Exception as e:
        raise click.ClickException(f'Error getting port configurations on switch {serial}.') from e


def update_switch_config(dashboard_api, source_device: SwitchDevice, target_serial: str):
    """Update switch configuration.

    Parameters
    ----------
    dashboard_api : meraki.DashboardAPI
        Meraki Dashboard API object.
    source_device : SwitchDevice
        Device configuration of the source switch.
    target_serial : str
        Serial number of switch to update.
    """
    click.secho(f'---- Updating switch configuration for {target_serial} ----', reverse=True, fg='cyan')

    source_device.name = f'{source_device.name}-clone'
    update_device_kwargs: dict = dataclasses.asdict(
        source_device, dict_factory=lambda x: {k: v for k, v in x if v is not None}
    )

    try:
        response = dashboard_api.devices.updateDevice(target_serial, **update_device_kwargs)
        click.echo(response)
    except Exception as e:
        raise click.ClickException(f'Error updating switch configuration for {target_serial}.') from e


def update_switch_ports(dashboard_api, source_ports: list[SwitchPort], target_serial: str, target_port_count: int):
    """Update switch port configuration.

    In the event that the number of ports on the source switch and target switch are found to be incompatible,
    this function will raise an exception before any modifications are made to the target switch ports.

    note:
    It doesn't appear to be possible to (directly) discern from port configs returned by the dashboard API
    whether a port is a GbE RJ45 port or one of the additional GbE SFP uplink ports.
    The assumption will be that the first 8, 24, or 48 ports are RJ45 and the rest are SFP uplinks.

    Parameters
    ----------
    dashboard_api : meraki.DashboardAPI
        Meraki Dashboard API object.
    source_ports : list[SwitchPort]
        Port configuration for each port on the source switch.
    target_serial : str
        Serial number of switch to update.
    target_port_count : int
        Number of ports on the target switch.
    """
    source_port_count: int = len(source_ports)
    if source_port_count == 0:
        raise click.ClickException(f'No ports found on source switch {target_serial}.')

    rj45_ports: list[int] = [8, 24, 48]

    # from the possible GbE RJ45 port counts, select either the number at or the nearest *below* the source port count
    source_rj45_count: int = min(rj45_ports, key=lambda x: abs(x - source_port_count) if x <= source_port_count else x)
    target_rj45_count: int = min(rj45_ports, key=lambda x: abs(x - target_port_count) if x <= target_port_count else x)

    source_rj45_ports: list[SwitchPort] = source_ports[:source_rj45_count]
    source_sfp_ports: list[SwitchPort] = source_ports[source_rj45_count:]

    # Handle mismatched port counts
    if source_rj45_count != target_rj45_count:
        if source_rj45_count == 24 and target_rj45_count == 48:
            for n in range(24, 48):
                source_rj45_ports.append(SwitchPort(**dataclasses.asdict(source_rj45_ports[0])))
                source_rj45_ports[n].portId = str(n + 1)
            for port in source_sfp_ports:
                port.portId = str(int(port.portId) + 24)
        elif source_rj45_count == 48 and target_rj45_count == 24:
            source_rj45_ports = source_rj45_ports[:24]
            for port in source_sfp_ports:
                port.portId = str(int(port.portId) - 24)
        else:
            raise click.BadParameter(
                f'Incompatible port counts ({source_rj45_count}-port switch -> {target_rj45_count}-port switch).'
            )

    adjusted_source_ports = source_rj45_ports + source_sfp_ports

    for port in adjusted_source_ports:
        click.secho(f'---- Updating port {port.portId} on {target_serial} ----', reverse=True, fg='bright_magenta')
        update_port_kwargs = dataclasses.asdict(
            port, dict_factory=lambda x: {k: v for k, v in x if v is not None and k != 'portId'}
        )
        try:
            response = dashboard_api.switch.updateDeviceSwitchPort(target_serial, port.portId, **update_port_kwargs)
            click.echo(response)
        except Exception as e:
            raise click.ClickException(f'Error updating port {port.portId} on switch {target_serial}.') from e


def clone_config(dashboard_api, organization_id: str, source_serial: str, target_serial: str):
    """Clone configuration from one switch to another of the same model.

    Cloning a switch configuration will only work if the source switch and target switch are the same model.
    See https://developer.cisco.com/meraki/api-v1/#!clone-organization-switch-devices for more information.

    Parameters
    ----------
    dashboard_api : meraki.DashboardAPI
        Meraki Dashboard API object.
    organization_id : str
        Meraki organization ID.
    source_serial : str
        Serial number of switch to clone from.
    target_serial : str
        Serial number of switch to clone to.
    """
    try:
        response = dashboard_api.switch.cloneOrganizationSwitchDevices(organization_id, source_serial, [target_serial])
        click.echo(response)
    except Exception as e:
        raise click.ClickException(f'Error cloning configuration from {source_serial} to {target_serial}.') from e


def get_api_key_from_env():
    """Get Meraki Dashboard API key from environment variable.

    Returns
    -------
    str
        Meraki Dashboard API key.
    """
    meraki_dashboard_api_key = os.environ.get('MERAKI_DASHBOARD_API_KEY')
    if meraki_dashboard_api_key is None:
        raise click.BadParameter('No API key provided. Please set the environment variable MERAKI_DASHBOARD_API_KEY.')
    return meraki_dashboard_api_key


@click.group()
@click.pass_context
def cli(ctx):
    """Migration utility for Meraki switches."""
    pass


@cli.command(
    context_settings=dict(help_option_names=['-h', '--help'], ignore_unknown_options=True),
    no_args_is_help=True,
    short_help='Display switch configuration by DEVICE_SERIAL.',
)
@click.argument('device-serial', type=click.STRING)
@click.option(
    '--api-key',
    '-a',
    type=click.STRING,
    default='MERAKI_DASHBOARD_API_KEY',
    help='Provide if env var MERAKI_DASHBOARD_API_KEY is not set.',
)
def display(api_key, device_serial):
    """Display switch configuration by DEVICE_SERIAL."""
    if api_key == 'MERAKI_DASHBOARD_API_KEY':
        api_key = get_api_key_from_env()

    try:
        dashboard_api = meraki.DashboardAPI(api_key, suppress_logging=True)

        click.secho('---- Switch device ----', reverse=True, fg='cyan')
        switch_device: SwitchDevice = get_switch_config(dashboard_api, device_serial)
        for f in dataclasses.fields(switch_device):
            if getattr(switch_device, f.name) is not None:
                click.secho(f'{f.name}: {getattr(switch_device, f.name)}', fg='cyan')

        switch_ports: list[SwitchPort] = get_switch_ports(dashboard_api, device_serial)
        for port in switch_ports:
            click.secho(f'---- Port {port.portId} ----', reverse=True, fg='bright_magenta')
            for f in dataclasses.fields(port):
                if getattr(port, f.name) is not None:
                    click.secho(f'{f.name}: {getattr(port, f.name)}', fg='bright_magenta')
    except Exception as e:
        raise click.ClickException(f'Error displaying switch configuration for {device_serial}.') from e


@cli.command(
    context_settings=dict(help_option_names=['-h', '--help'], ignore_unknown_options=True),
    no_args_is_help=True,
    short_help='Copy Meraki switch device configuration and port configurations.',
)
@click.argument('source-serial', type=click.STRING)
@click.argument('target-serial', type=click.STRING)
@click.option(
    '--api-key',
    '-a',
    type=click.STRING,
    default='MERAKI_DASHBOARD_API_KEY',
    help='Provide if env var MERAKI_DASHBOARD_API_KEY is not set.',
)
@click.option(
    '--organization-id', '-o', type=click.STRING, default=None, help='Provide if source and target are the same model.'
)
@click.option('--quiet', '-q', is_flag=True, help='Suppress dashboard API logging.')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt.')
@click.pass_context
def migrate(ctx, api_key, organization_id, quiet, yes, source_serial, target_serial):
    """Copy Meraki switch device configuration and port configurations.

    If migrating to a switch of the same model, provide the ORGANIZATION_ID and the configuration will be cloned using
    the Meraki Dashboard API call 'Clone Organization Switch Devices' (more configs may be migrated this way).

    \b
    Three conditions are required before the target switch will be modified:
    1. The target switch 'name' is NOT the same as its mac address.
    2. The target switch 'tags' include the 'undeployed' tag.
    3. The number of ports on each switch matches one of the following scenarios:
         8-port  ->   8-port
        24-port  ->  24-port
        48-port  ->  48-port
        24-port  ->  48-port (ports 1-24 are copied over; port 1 is duplicated to ports 25-48)
        48-port  ->  24-port (ports 1-24 on the source switch are copied over and 25-48 are ignored)

    SOURCE_SERIAL: Serial number of the switch to copy configuration from.
    TARGET_SERIAL: Serial numbers of one or more target switches.
    """
    if api_key == 'MERAKI_DASHBOARD_API_KEY':
        api_key = get_api_key_from_env()

    try:
        dashboard_api = meraki.DashboardAPI(api_key, suppress_logging=quiet)

        source_device: SwitchDevice = get_switch_config(dashboard_api, source_serial)
        target_device: SwitchDevice = get_switch_config(dashboard_api, target_serial)

        click.secho('---- Source device ----', reverse=True, fg='cyan')
        for f in dataclasses.fields(source_device):
            if getattr(source_device, f.name) is not None:
                click.secho(f'{f.name}: {getattr(source_device, f.name)}', fg='cyan')

        click.secho('---- Target device ----', reverse=True, fg='cyan')
        for f in dataclasses.fields(target_device):
            if getattr(target_device, f.name) is not None:
                click.secho(f'{f.name}: {getattr(target_device, f.name)}', fg='cyan')

        update_allowed_tag = 'undeployed'

        if target_device.name == target_device.mac:
            raise click.ClickException(f'Target switch {target_serial} appears to be in use (name = mac address).')
        elif update_allowed_tag not in target_device.tags:
            raise click.ClickException(f'Target switch {target_serial} does not have the "{update_allowed_tag}" tag.')
        elif not yes:
            click.confirm(f'Continue copying configuration from {source_serial} to {target_serial}?', abort=True)
        else:
            click.echo(f'Copying configuration from {source_serial} to {target_serial}...')

        source_ports: list[SwitchPort] = get_switch_ports(dashboard_api, source_serial)
        target_ports: list[SwitchPort] = get_switch_ports(dashboard_api, target_serial)

        # If the source switch and target switch are the same model, use API call 'Clone Organization Switch Devices'
        if source_device.model == target_device.model and organization_id is not None:
            clone_config(dashboard_api, organization_id, source_serial, target_serial)

        update_switch_ports(dashboard_api, source_ports, target_serial, len(target_ports))
        update_switch_config(dashboard_api, source_device, target_serial)

    except meraki.APIError as e:
        click.secho(f'Error migrating switch configuration: {e}', reverse=True, fg='red')
        ctx.abort()


@cli.command(
    context_settings=dict(help_option_names=['-h', '--help'], ignore_unknown_options=True),
    no_args_is_help=True,
    short_help='Adds "undeployed" to the tags attribute of a switch device.',
)
@click.argument('device-serial', type=click.STRING)
@click.option(
    '--api-key',
    '-a',
    type=click.STRING,
    default='MERAKI_DASHBOARD_API_KEY',
    help='Provide if env var MERAKI_DASHBOARD_API_KEY is not set.',
)
@click.pass_context
def tag(ctx, api_key, device_serial):
    """Add "undeployed" to the tags attribute of a switch device."""
    if api_key == 'MERAKI_DASHBOARD_API_KEY':
        api_key = get_api_key_from_env()

    try:
        dashboard_api = meraki.DashboardAPI(api_key, suppress_logging=True)

        device: SwitchDevice = get_switch_config(dashboard_api, device_serial)

        click.secho('---- Switch device ----', reverse=True, fg='cyan')
        for f in dataclasses.fields(device):
            if getattr(device, f.name) is not None:
                click.secho(f'{f.name}: {getattr(device, f.name)}', fg='cyan')

        click.secho('Adding "undeployed" tag...', fg='bright_green')
        device.tags.append('undeployed')
        device_kwargs = {'tags': device.tags}

        response = dashboard_api.devices.updateDevice(device_serial, **device_kwargs)
        click.echo(response)

        click.secho('---- Updated device config ----', reverse=True, fg='bright_green')
        switch_device: SwitchDevice = get_switch_config(dashboard_api, device_serial)
        for f in dataclasses.fields(switch_device):
            if getattr(switch_device, f.name) is not None:
                click.secho(f'{f.name}: {getattr(switch_device, f.name)}', fg='bright_green')
    except meraki.APIError:
        click.secho(f'Error adding tag to switch {device_serial}.', reverse=True, fg='bright_red')
        ctx.abort()
