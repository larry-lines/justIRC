"""
Dependency Injection Container for JustIRC Client

Provides inversion of control for better testability and maintainability.
All dependencies are registered and resolved through this container.
"""

from typing import Dict, Any, Callable, Optional, TypeVar, Type
from dataclasses import dataclass

from crypto_layer import CryptoLayer
from image_transfer import ImageTransfer
from config_manager import ConfigManager
from message_formatter import MessageFormatter

from services import (
    NetworkService,
    StateManager,
    MessageService,
    ChannelService,
    NotificationService
)
from presenter import ClientPresenter


T = TypeVar('T')


@dataclass
class ServiceDescriptor:
    """Describes how to create and manage a service"""
    factory: Callable
    singleton: bool = True
    instance: Optional[Any] = None


class DependencyContainer:
    """
    Simple dependency injection container.
    
    Manages the lifecycle of services and their dependencies.
    Supports singleton and transient lifetimes.
    """
    
    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._instances: Dict[Type, Any] = {}
    
    def register_singleton(self, service_type: Type[T], factory: Callable[[], T]):
        """
        Register a singleton service (created once and reused)
        
        Args:
            service_type: The type/interface of the service
            factory: Factory function that creates the service
        """
        self._services[service_type] = ServiceDescriptor(
            factory=factory,
            singleton=True
        )
    
    def register_transient(self, service_type: Type[T], factory: Callable[[], T]):
        """
        Register a transient service (created each time it's resolved)
        
        Args:
            service_type: The type/interface of the service
            factory: Factory function that creates the service
        """
        self._services[service_type] = ServiceDescriptor(
            factory=factory,
            singleton=False
        )
    
    def register_instance(self, service_type: Type[T], instance: T):
        """
        Register an existing instance as a singleton
        
        Args:
            service_type: The type/interface of the service
            instance: The actual instance to register
        """
        self._services[service_type] = ServiceDescriptor(
            factory=lambda: instance,
            singleton=True,
            instance=instance
        )
        self._instances[service_type] = instance
    
    def resolve(self, service_type: Type[T]) -> T:
        """
        Resolve a service from the container
        
        Args:
            service_type: The type/interface to resolve
        
        Returns:
            The service instance
        
        Raises:
            KeyError: If service type is not registered
        """
        if service_type not in self._services:
            raise KeyError(f"Service {service_type.__name__} not registered")
        
        descriptor = self._services[service_type]
        
        # Return existing instance for singletons
        if descriptor.singleton and descriptor.instance is not None:
            return descriptor.instance
        
        # Create new instance
        instance = descriptor.factory()
        
        # Store singleton instance
        if descriptor.singleton:
            descriptor.instance = instance
            self._instances[service_type] = instance
        
        return instance
    
    def try_resolve(self, service_type: Type[T]) -> Optional[T]:
        """
        Try to resolve a service, returns None if not registered
        
        Args:
            service_type: The type/interface to resolve
        
        Returns:
            The service instance or None
        """
        try:
            return self.resolve(service_type)
        except KeyError:
            return None
    
    def is_registered(self, service_type: Type) -> bool:
        """Check if a service type is registered"""
        return service_type in self._services
    
    def clear(self):
        """Clear all registrations"""
        self._services.clear()
        self._instances.clear()


class ContainerBuilder:
    """
    Fluent builder for configuring the dependency container
    """
    
    def __init__(self):
        self.container = DependencyContainer()
        self._config: Optional[ConfigManager] = None
    
    def with_config(self, config: ConfigManager) -> 'ContainerBuilder':
        """Set configuration manager"""
        self._config = config
        return self
    
    def build_default(self) -> DependencyContainer:
        """
        Build container with default JustIRC client configuration
        """
        # Configuration (if not provided, create default)
        if self._config is None:
            self._config = ConfigManager()
        
        self.container.register_instance(ConfigManager, self._config)
        
        # Crypto layer (singleton)
        self.container.register_singleton(
            CryptoLayer,
            lambda: CryptoLayer()
        )
        
        # Message formatter (singleton)
        self.container.register_singleton(
            MessageFormatter,
            lambda: MessageFormatter()
        )
        
        # Image transfer (singleton)
        self.container.register_singleton(
            ImageTransfer,
            lambda: ImageTransfer(self.container.resolve(CryptoLayer))
        )
        
        # State manager (singleton)
        self.container.register_singleton(
            StateManager,
            lambda: StateManager()
        )
        
        # Network service (singleton)
        self.container.register_singleton(
            NetworkService,
            lambda: NetworkService(self.container.resolve(CryptoLayer))
        )
        
        # Message service (singleton)
        self.container.register_singleton(
            MessageService,
            lambda: MessageService(
                network=self.container.resolve(NetworkService),
                state=self.container.resolve(StateManager),
                crypto=self.container.resolve(CryptoLayer),
                image_transfer=self.container.resolve(ImageTransfer)
            )
        )
        
        # Channel service (singleton)
        self.container.register_singleton(
            ChannelService,
            lambda: ChannelService(
                network=self.container.resolve(NetworkService),
                state=self.container.resolve(StateManager),
                crypto=self.container.resolve(CryptoLayer)
            )
        )
        
        # Notification service (singleton)
        self.container.register_singleton(
            NotificationService,
            lambda: NotificationService(
                config=self._config.config if self._config else {}
            )
        )
        
        # Presenter (singleton)
        self.container.register_singleton(
            ClientPresenter,
            lambda: ClientPresenter(
                network_service=self.container.resolve(NetworkService),
                state_manager=self.container.resolve(StateManager),
                message_service=self.container.resolve(MessageService),
                channel_service=self.container.resolve(ChannelService),
                notification_service=self.container.resolve(NotificationService)
            )
        )
        
        return self.container
    
    def build_for_testing(self) -> DependencyContainer:
        """
        Build container with mock implementations for testing
        Can be customized by replacing specific services after building
        """
        return self.build_default()


def create_default_container(config: Optional[ConfigManager] = None) -> DependencyContainer:
    """
    Helper function to create a fully configured container
    
    Args:
        config: Optional configuration manager
    
    Returns:
        Configured dependency container
    """
    builder = ContainerBuilder()
    
    if config:
        builder.with_config(config)
    
    return builder.build_default()


def create_testing_container() -> DependencyContainer:
    """
    Helper function to create a container for testing
    
    Returns:
        Container configured for testing
    """
    builder = ContainerBuilder()
    return builder.build_for_testing()


# Example usage:
"""
# In production code:
container = create_default_container()
presenter = container.resolve(ClientPresenter)

# In tests:
container = create_testing_container()
# Replace services with mocks
container.register_instance(NetworkService, mock_network_service)
presenter = container.resolve(ClientPresenter)

# Custom configuration:
builder = ContainerBuilder()
builder.with_config(my_config)
container = builder.build_default()
"""
