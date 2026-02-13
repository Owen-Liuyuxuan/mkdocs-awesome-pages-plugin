"""Tests for time-based homepage logic and AI-report filtering."""
from unittest import mock

from ...navigation import AwesomeNavigation
from ...options import Options
from .base import NavigationTestCase


class TestHomepageTime(NavigationTestCase):
    """Tests for _safe_parse_time, shown_in_homepage, and page_list ordering."""

    def test_missing_time_no_exception(self):
        """Pages with no time field must not raise; use sentinel for ordering."""
        # _get_meta mock sets meta={}, so time is missing
        nav = self.createAwesomeNavigation([self.page("a"), self.page("b"), self.page("c")])
        result = nav.to_mkdocs()
        self.assertEqual(len(result.pages), 3)

    def test_malformed_time_no_exception(self):
        """Malformed time in front matter must not raise."""
        def _set_malformed_meta(page):
            page.meta = {"time": "not-a-date"}

        with mock.patch(
            "mkdocs_awesome_pages_plugin.navigation.AwesomeNavigation._get_meta",
            side_effect=_set_malformed_meta,
        ):
            nav = self.createAwesomeNavigation([self.page("x"), self.page("y")])
            result = nav.to_mkdocs()
        self.assertEqual(len(result.pages), 2)

    def test_prefix_empty_legacy_behavior(self):
        """When ai_report_path_prefix is empty, behavior matches legacy (no AI-specific logic)."""
        options = Options(
            filename=".pages",
            collapse_single_pages=False,
            strict=True,
            maximum_file_homepage=10,
            maximum_days_ahead=365,
            ai_report_path_prefix="",  # legacy
            ai_report_recent_limit=0,
            ai_report_pin_to_top=False,
        )
        nav = AwesomeNavigation(
            [self.page("1"), self.page("2"), self.page("3")],
            options,
            docs_dir="",
            explicit_sections=set(),
        )
        result = nav.to_mkdocs()
        self.assertEqual(len(result.pages), 3)
        self.assertValidNavigation(result)

    def test_prefix_set_with_limit_and_pin(self):
        """When prefix, limit, and pin are set, AI-report pages are capped and pinned."""
        def _meta_with_time(page):
            # Simulate time: ai reports get recent dates, others get old
            # Use dates within maximum_days_ahead=365 from "today" (test may run in any year)
            from datetime import datetime, timedelta

            path = page.file.src_path
            if path.startswith("reports/"):
                # Recent: 30 days ago from today
                recent = (datetime.today() - timedelta(days=30)).strftime("%Y%m%d")
                page.meta = {"time": recent}
            else:
                page.meta = {"time": "20200101"}  # old

        with mock.patch(
            "mkdocs_awesome_pages_plugin.navigation.AwesomeNavigation._get_meta",
            side_effect=_meta_with_time,
        ):
            nav = self.createAwesomeNavigation(
                [
                    self.page("Other", "other.md"),
                    self.page("Report1", "reports/2025-01.md"),
                    self.page("Report2", "reports/2025-02.md"),
                    self.page("Report3", "reports/2025-03.md"),
                ],
                maximum_file_homepage=20,
                maximum_days_ahead=365,
                ai_report_path_prefix="reports/",
                ai_report_recent_limit=2,
                ai_report_pin_to_top=True,
            )
            result = nav.to_mkdocs()

        pages = result.pages
        self.assertEqual(len(pages), 4)

        # With pin_to_top: reports (by recency) first, then others. No homepage in this set.
        paths = [p.file.src_path for p in pages]
        report_paths = [p for p in paths if p.startswith("reports/")]
        other_paths = [p for p in paths if not p.startswith("reports/")]
        self.assertEqual(len(report_paths), 3)
        self.assertEqual(len(other_paths), 1)
        # Reports should come before other
        first_report_idx = paths.index(report_paths[0])
        other_idx = paths.index(other_paths[0])
        self.assertLess(first_report_idx, other_idx)

        # Only 2 AI-report pages should get shown_in_homepage (limit=2)
        ai_shown = sum(
            1
            for p in pages
            if p.file.src_path.startswith("reports/") and getattr(p, "shown_in_homepage", False)
        )
        self.assertEqual(ai_shown, 2, f"Expected 2 AI reports shown, got {ai_shown}. Pages: {[(p.file.src_path, getattr(p, 'shown_in_homepage', '?')) for p in pages]}")
