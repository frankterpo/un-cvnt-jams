
import pytest
from unittest.mock import MagicMock, patch
from agent.browser_providers.novnc_provider import NoVNCProvider
from agent.browser_providers.base import BrowserProviderError

@patch("agent.browser_providers.novnc_provider.docker")
def test_novnc_provider_start_session(mock_docker):
    # Setup Mocks
    mock_client = MagicMock()
    mock_docker.from_env.return_value = mock_client
    
    mock_container = MagicMock()
    mock_container.status = 'running'
    mock_container.id = 'container_123'
    # Mock ports: 9515 -> 32768, 6080 -> 32769
    mock_container.ports.get.side_effect = lambda k: [{'HostPort': '32768'}] if k == '9515/tcp' else [{'HostPort': '32769'}]
    
    # Mock start flow
    mock_client.containers.run.return_value = mock_container
    
    provider = NoVNCProvider()
    
    # Mock Profile Row
    mock_profile = MagicMock()
    mock_profile.id = 1
    mock_profile.dummy_account.name = "testuser"
    
    # Mock socket check to be always open
    with patch.object(provider, '_is_port_open', return_value=True):
        session = provider.start_session(mock_profile, trace_id="trace-1")
    
    assert session.provider_code == "NOVNC"
    assert session.provider_session_ref == "container_123"
    assert "32768" in session.webdriver_url
    assert "32769" in session.novnc_url
    
    # Verify Docker call
    mock_client.containers.run.assert_called_once()
    args, kwargs = mock_client.containers.run.call_args
    assert "social/novnc-browser:latest" in args or kwargs.get('image')
    assert "novnc-testuser" in kwargs['name']

@patch("agent.browser_providers.novnc_provider.docker")
def test_novnc_provider_stop_session(mock_docker):
    mock_client = MagicMock()
    mock_docker.from_env.return_value = mock_client
    mock_container = MagicMock()
    mock_client.containers.get.return_value = mock_container
    
    provider = NoVNCProvider()
    session = MagicMock()
    session.provider_session_ref = "container_123"
    
    provider.stop_session(session, trace_id="trace-1")
    
    mock_client.containers.get.assert_called_with("container_123")
    mock_container.stop.assert_called_once()
    mock_container.remove.assert_called_once()
