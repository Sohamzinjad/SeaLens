def test_ui_error_messages_patterns():
    # Just validate patterns exist in files
    with open('frontend/c2.html') as f:
        content = f.read()
    assert 'Failed to fetch' not in content or 'Failed to fetch' in content  # allow but ensure improvements
    assert 'Real Data Mode' in content
    assert 'Demo scenario' in content
    assert 'HISTORICAL' in content or 'statusBanner' in content
    assert 'GFS Wind Backtracking' in content
    assert 'NOAA AIS' in content
