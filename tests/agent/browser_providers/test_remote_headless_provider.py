
import pytest
from unittest.mock import MagicMock, patch
from agent.browser_providers.remote_headless_provider import RemoteHeadlessProvider, BrowserProviderError

@patch("agent.browser_providers.remote_headless_provider.docker")
def test_remote_headless_start_session(mock_docker):
    # Setup Mocks
    mock_client = MagicMock()
    mock_docker.from_env.return_value = mock_client
    
    # Mock Container
    mock_container = MagicMock()
    mock_container.status = 'running'
    mock_container.id = 'container_remote_123'
    # Mock Port mapping: 4444 -> 33333 on host
    mock_container.ports.get.return_value = [{'HostPort': '33333'}]
    mock_client.containers.run.return_value = mock_container
    
    provider = RemoteHeadlessProvider()
    
    # Mock Profile
    mock_profile = MagicMock()
    mock_profile.id = 10
    mock_profile.dummy_account.name = "remoteuser"
    mock_profile.provider.config = {"default_webdriver_port": 4444}
    
    # Mock Port Open check
    with patch.object(provider, '_is_port_open', return_value=True):
         # Mock DOCKER_HOST env
         with patch.dict('os.environ', {'DOCKER_HOST': 'tcp://192.168.1.50:2375'}):
             session = provider.start_session(mock_profile, trace_id="trace-remote")
             
             assert session.provider_code == "REMOTE_HEADLESS"
             assert session.provider_session_ref == "container_remote_123"
             # Verify URL reflects remote host IP
             assert "http://192.168.1.50:33333/wd/hub" == session.webdriver_url

@patch("agent.browser_providers.remote_headless_provider.docker")
def test_remote_headless_stop_session(mock_docker):
    mock_client = MagicMock()
    mock_docker.from_env.return_value = mock_client
    
    mock_container = MagicMock()
    mock_client.containers.get.return_value = mock_container
    
    provider = RemoteHeadlessProvider()
    session = MagicMock()
    session.provider_session_ref = "cid_999"
    
    provider.stop_session(session, trace_id="trace-stop")
    
    mock_client.containers.get.assert_called_with("cid_999")
    mock_container.stop.assert_called_once()
    mock_container.remove.assert_called_once()
