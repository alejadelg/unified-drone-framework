"""DroneManager: multi-drone orchestration through the unified interface.

DroneManager never references concrete adapter classes — it works entirely
through DroneRegistry.create() and the DroneAdapter abstract interface.
"""

import logging
from typing import Any, Dict, List

from .base_adapter import DroneAdapter
from .enums import DroneStatus
from .exceptions import DroneError
from .models import DroneCommand
from .registry import DroneRegistry

logger = logging.getLogger(__name__)


class DroneManager:
    """Manages multiple drones and dispatches commands to them."""

    def __init__(self) -> None:
        self._drones: Dict[str, DroneAdapter] = {}

    def add_drone(self, drone_id: str, adapter_key: str, **kwargs: Any) -> DroneAdapter:
        """Create and register a drone instance.

        Args:
            drone_id: User-chosen identifier (e.g., "drone_alpha").
            adapter_key: Registry key (e.g., "codrone_edu").
            **kwargs: Passed to the adapter constructor.

        Returns:
            The created DroneAdapter instance.
        """
        adapter = DroneRegistry.create(adapter_key, **kwargs)
        self._drones[drone_id] = adapter
        logger.info("Added drone '%s' using adapter '%s'", drone_id, adapter_key)
        return adapter

    def remove_drone(self, drone_id: str) -> None:
        """Remove a drone, disconnecting it first if necessary."""
        drone = self._drones.pop(drone_id, None)
        if drone and drone.status != DroneStatus.DISCONNECTED:
            try:
                drone.disconnect()
            except DroneError as e:
                logger.error("Error disconnecting '%s': %s", drone_id, e)

    def get_drone(self, drone_id: str) -> DroneAdapter:
        """Retrieve a managed drone by its ID."""
        if drone_id not in self._drones:
            raise DroneError(f"Unknown drone: '{drone_id}'")
        return self._drones[drone_id]

    def send_command(self, drone_id: str, command: DroneCommand) -> Any:
        """Send a command to a single drone by ID."""
        drone = self.get_drone(drone_id)
        logger.info("Sending %s to '%s'", command.action.name, drone_id)
        return drone.execute(command)

    def broadcast_command(self, command: DroneCommand) -> Dict[str, Any]:
        """Send the same command to ALL managed drones.

        Returns a dict mapping drone_id to the result (or exception on failure).
        """
        results: Dict[str, Any] = {}
        for drone_id, drone in self._drones.items():
            try:
                logger.info("Broadcasting %s to '%s'", command.action.name, drone_id)
                results[drone_id] = drone.execute(command)
            except DroneError as e:
                logger.error("Error on '%s': %s", drone_id, e)
                results[drone_id] = e
        return results

    def send_sequence(self, drone_id: str, commands: List[DroneCommand]) -> List[Any]:
        """Execute an ordered sequence of commands on one drone."""
        return [self.send_command(drone_id, cmd) for cmd in commands]

    @property
    def drone_ids(self) -> List[str]:
        """Return all managed drone IDs."""
        return list(self._drones.keys())

    def status_report(self) -> Dict[str, str]:
        """Return a dict mapping drone_id to its current status name."""
        return {did: drone.status.name for did, drone in self._drones.items()}
