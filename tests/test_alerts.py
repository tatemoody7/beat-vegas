from beatvegas.alerts.detect import Alert, detect_line_alerts, format_alert

MATCHUPS = {1: "Michigan @ Ohio State", 2: "LSU @ Alabama", 3: "Iowa @ Wisconsin"}


def test_newly_posted_alert():
    prev = {}                              # nothing seen yet
    new = {1: 24.5}
    alerts = detect_line_alerts(prev, new, MATCHUPS)
    assert len(alerts) == 1
    assert alerts[0].kind == "posted" and alerts[0].new_line == 24.5


def test_significant_move_alert():
    prev = {2: 27.0}
    new = {2: 25.5}                        # moved 1.5 >= threshold 1.0
    alerts = detect_line_alerts(prev, new, MATCHUPS, threshold=1.0)
    assert len(alerts) == 1 and alerts[0].kind == "move"
    assert alerts[0].old_line == 27.0 and alerts[0].new_line == 25.5


def test_small_move_below_threshold_ignored():
    alerts = detect_line_alerts({3: 24.0}, {3: 24.5}, MATCHUPS, threshold=1.0)
    assert alerts == []


def test_scores_attached_and_unchanged_ignored():
    prev = {1: 24.5}
    new = {1: 24.5}                        # no change
    alerts = detect_line_alerts(prev, new, MATCHUPS, scores={1: 63})
    assert alerts == []


def test_posted_includes_score():
    alerts = detect_line_alerts({}, {1: 22.0}, MATCHUPS, scores={1: 70})
    assert alerts[0].model_score == 70


def test_format_posted_and_move():
    posted = format_alert(Alert(1, "posted", "Michigan @ Ohio State", 24.5, model_score=63))
    assert "posted" in posted and "24.5" in posted and "63" in posted
    up = format_alert(Alert(2, "move", "LSU @ Alabama", 26.0, old_line=24.5))
    assert "↑" in up and "24.5" in up and "26" in up
    down = format_alert(Alert(2, "move", "LSU @ Alabama", 23.0, old_line=25.0))
    assert "↓" in down
