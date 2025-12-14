
import pytest
from unittest.mock import MagicMock, patch
from agent.services.browser_provider_allocator import BrowserProviderAllocator
from agent.browser_providers.base import BrowserProviderError, BrowserSession

@patch("agent.services.browser_provider_allocator.GoLoginProvider")
@patch("agent.services.browser_provider_allocator.NovncAwsProvider")
@patch("agent.services.browser_provider_allocator.load_settings")
def test_allocator_fallback_logic(mock_settings, MockNovnc, MockGoLogin):
    # Setup Mocks
    mock_settings.return_value.max_novnc_concurrent_sessions = 2
    
    allocator = BrowserProviderAllocator()
    # Inject mocked instances
    mock_gologin = MockGoLogin.return_value
    mock_novnc = MockNovnc.return_value
    allocator.providers = {
        "GOLOGIN": mock_gologin,
        "NOVNC_AWS": mock_novnc
    }
    
    # Mock Session & Profiles
    mock_db_session = MagicMock()
    
    # Mock Profiles: 1 GoLogin, 1 NOVNC_AWS
    p1 = MagicMock()
    p1.provider.code = "GOLOGIN"
    p2 = MagicMock()
    p2.provider.code = "NOVNC_AWS"
    
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = [p1, p2]
    
    # Scenario 1: GoLogin Succeeds
    mock_gologin.start_session.return_value = BrowserSession(provider_code="GOLOGIN", provider_profile_id=1, provider_session_ref="sess1", webdriver_url="url1")
    
    session = allocator.allocate_for_dummy_account(mock_db_session, dummy_account_id=1)
    assert session.provider_code == "GOLOGIN"
    mock_gologin.start_session.assert_called()
    mock_novnc.start_session.assert_not_called()
    
    # Reset
    mock_gologin.reset_mock()
    mock_novnc.reset_mock()
    
    # Scenario 2: GoLogin Fails (Limit) -> Fallback to NOVNC_AWS
    mock_gologin.start_session.side_effect = BrowserProviderError("Limit Reached", code="GOLOGIN_LIMIT_REACHED")
    mock_novnc.start_session.return_value = BrowserSession(provider_code="NOVNC_AWS", provider_profile_id=2, provider_session_ref="sess2", webdriver_url="url2")
    
    # Mock cost control to return 0 active
    with patch.object(allocator, '_count_active_novnc_sessions', return_value=0):
        session = allocator.allocate_for_dummy_account(mock_db_session, dummy_account_id=1)
        assert session.provider_code == "NOVNC_AWS"
        mock_gologin.start_session.assert_called()
        mock_novnc.start_session.assert_called()

    # Reset
    mock_gologin.reset_mock()
    mock_novnc.reset_mock()
    
    # Scenario 3: GoLogin Fails, NOVNC Throttled
    mock_gologin.start_session.side_effect = BrowserProviderError("Limit", code="GOLOGIN_LIMIT")
    
    # Mock cost control to return 2 active (>= limit)
    with patch.object(allocator, '_count_active_novnc_sessions', return_value=2):
        with pytest.raises(BrowserProviderError) as exc:
            allocator.allocate_for_dummy_account(mock_db_session, dummy_account_id=1)
        
        assert "All providers exhausted" in str(exc.value)
        # Should not have called start_session on novnc
        mock_novnc.start_session.assert_not_called()
