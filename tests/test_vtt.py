# -*- coding: utf-8 -*-
from reachkit.adapters.youtube import parse_vtt

SAMPLE = """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:03.000
Hello <c.colorE5E5E5>world</c>

00:00:03.000 --> 00:00:05.000
Hello world

00:00:05.000 --> 00:00:07.000
Second line
"""


def test_parse_vtt_strips_and_dedupes():
    out = parse_vtt(SAMPLE)
    assert out.splitlines() == ["Hello world", "Second line"]
