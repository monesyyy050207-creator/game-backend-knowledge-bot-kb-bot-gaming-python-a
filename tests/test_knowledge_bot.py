from src.knowledge_bot import GameAsset, choose_action


def test_high_risk_player_asset_enters_review() -> None:
    decision = choose_action(GameAsset("skin-184", "player-skin", 0.91))
    assert decision.action == "review"
    assert decision.reason == "high moderation risk"
