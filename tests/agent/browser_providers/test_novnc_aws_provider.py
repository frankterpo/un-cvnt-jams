
import pytest
from unittest.mock import MagicMock, patch
from agent.browser_providers.novnc_aws_provider import NovncAwsProvider, BrowserProviderError

@patch("agent.browser_providers.novnc_aws_provider.docker")
def test_novnc_aws_start_session(mock_docker):
    # Setup Mocks
    mock_client = MagicMock()
    # Mock APIError so it can be caught
    mock_docker.errors.APIError = type("APIError", (Exception,), {})
    mock_docker.from_env.return_value = mock_client
    
    # Mock Container
    mock_container = MagicMock()
    mock_container.status = 'running'
    mock_container.id = 'aws_container_123'
    # Mock Port mappings
    mock_container.ports.get.side_effect = lambda k: [{'HostPort': '32000'}] if k == '4444/tcp' else [{'HostPort': '32001'}]
    mock_client.containers.run.return_value = mock_container
    
    provider = NovncAwsProvider()
    
    # Mock Profile
    mock_profile = MagicMock()
    mock_profile.provider.config = {"docker_image": "social/novnc-browser:latest", "default_webdriver_port": 4444}
    mock_profile.dummy_account.name = "awsuser"
    
    # Mock Socket check & Host resolution
    with patch.object(provider, '_is_port_open', return_value=True):
        with patch.dict('os.environ', {'DOCKER_HOST': 'tcp://54.1.2.3:2375'}):
             session = provider.start_session(mock_profile, trace_id="trace-aws")
             
             assert session.provider_code == "NOVNC_AWS"
             assert session.provider_session_ref == "aws_container_123"
             # Verify Remote IP usage
             assert "http://54.1.2.3:32000" in session.webdriver_url
             assert "http://54.1.2.3:32001" in session.novnc_url

@patch("agent.browser_providers.novnc_aws_provider.docker")
@patch("agent.browser_providers.novnc_aws_provider.time.sleep")
def test_novnc_aws_start_session_timeout(mock_sleep, mock_docker):
    mock_client = MagicMock()
    # Mock APIError so it can be caught
    mock_docker.errors.APIError = type("APIError", (Exception,), {})
    mock_docker.from_env.return_value = mock_client
    
    mock_container = MagicMock()
    mock_container.status = 'running'
    # Mock ports return None always
    mock_container.ports.get.return_value = None
    mock_client.containers.run.return_value = mock_container
    
    provider = NovncAwsProvider()
    mock_profile = MagicMock()
    mock_profile.dummy_account.name = "awsuser"

    with patch.object(provider, '_is_port_open', return_value=False):
        with pytest.raises(BrowserProviderError) as exc:
             provider.start_session(mock_profile, trace_id="trace-fail")
        
        assert "Timed out" in str(exc.value)
        mock_container.stop.assert_called()
        mock_container.remove.assert_called()

