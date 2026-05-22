"""Coarse performance budgets — protect against accidental O(N²) regressions.

These aren't benchmarks in the strict sense; they're sanity ceilings on
the operations that run every time the user opens a panel or the tick
fires. If we ever cross them, something has gone badly wrong.
"""

from __future__ import annotations

import time


def _elapsed(fn, *a, **kw):
    t0 = time.perf_counter()
    fn(*a, **kw)
    return time.perf_counter() - t0


def test_list_bag_100_buddies_under_100ms(store, temp_assets, no_network):
    """Bag panel opens cold — we want this fast even with a hundred caught
    individuals across the registry."""
    for _ in range(100):
        store.add_to_bag(1)
    elapsed = _elapsed(store.list_bag)
    assert elapsed < 0.1, (
        f"list_bag(100 rows) took {elapsed*1000:.1f}ms, target <100ms"
    )


def test_list_dex_300_entries_under_50ms(store, temp_assets, no_network):
    """Dex panel reads the whole table to build the summary."""
    for i in range(1, 301):
        store.record_catch(i, f"#{i:04d}")
    elapsed = _elapsed(store.list_dex)
    assert elapsed < 0.05, (
        f"list_dex(300 entries) took {elapsed*1000:.1f}ms, target <50ms"
    )


def test_record_catch_burst_100_under_500ms(store, temp_assets, no_network):
    """Backfilling a fresh user's dex shouldn't crawl."""
    t0 = time.perf_counter()
    for i in range(1, 101):
        store.record_catch(i, f"name-{i}")
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.5, (
        f"100 record_catch calls took {elapsed*1000:.1f}ms, target <500ms"
    )


def test_get_bag_entry_lookup_under_5ms(store, temp_assets, no_network):
    """Per-card lookups in the bag panel — each card calls this."""
    buddies = [store.add_to_bag(i % 151 + 1) for i in range(50)]
    elapsed = _elapsed(store.get_bag_entry, buddies[-1].bag_id)
    assert elapsed < 0.005, (
        f"get_bag_entry took {elapsed*1000:.2f}ms, target <5ms"
    )


def test_display_scale_lookup_under_1ms(temp_assets, no_network):
    """Sprite_widget asks this every time it loads a sprite."""
    from pokemon_buddy.display_scale import get
    elapsed = _elapsed(get, 25)
    assert elapsed < 0.001, (
        f"display_scale.get took {elapsed*1000:.3f}ms, target <1ms"
    )


def test_custom_pokemon_add_under_200ms(temp_assets, no_network, tmp_path):
    """Adding a single custom pokemon — UI calls this on Add button click."""
    from pokemon_buddy import custom_pokemon
    gif = tmp_path / "tiny.gif"
    gif.write_bytes(
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
        b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00"
        b"\x02\x02D\x01\x00;"
    )
    elapsed = _elapsed(custom_pokemon.add, "테스트", gif)
    assert elapsed < 0.2, (
        f"custom_pokemon.add took {elapsed*1000:.1f}ms, target <200ms"
    )
