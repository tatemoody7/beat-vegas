"""validate_engine.py must be runnable on the same DB with and without the FBS
filter so the filter's effect can be measured like-for-like."""


def test_parse_args_defaults_to_fbs_only(load_script):
    mod = load_script("validate_engine")
    args = mod.parse_args([])
    assert args.fbs_only is True


def test_all_divisions_flag_disables_the_fbs_filter(load_script):
    mod = load_script("validate_engine")
    args = mod.parse_args(["--all-divisions"])
    assert args.fbs_only is False
