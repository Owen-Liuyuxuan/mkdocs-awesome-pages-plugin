import warnings
from datetime import datetime
from pathlib import Path
from natsort import natsort_keygen
from typing import List, Optional, Union, Set

from mkdocs.structure.nav import (
    Navigation as MkDocsNavigation,
    Section,
    Link,
    _add_parent_links,
    _add_previous_and_next_links,
)
from mkdocs.structure.pages import Page

from .meta import Meta, MetaNavItem, MetaNavRestItem, RestItemList
from .options import Options
from .utils import dirname, basename, join_paths

import io
from mkdocs.utils import meta as mkdocs_meta

NavigationItem = Union[Page, Section, Link]


class NavEntryNotFound(Warning):
    def __init__(self, entry: str, context: str):
        super().__init__('Nav entry "{entry}" not found. [{context}]'.format(entry=entry, context=context))


class TitleInRootHasNoEffect(Warning):
    def __init__(self, filename: str):
        super().__init__(
            'Using the "title" attribute in the {filename} file of the doc root has no effect'.format(filename=filename)
        )


class HideInRootHasNoEffect(Warning):
    def __init__(self, filename: str):
        super().__init__(
            'Using the "hide" attribute in the {filename} file of the doc root has no effect'.format(filename=filename)
        )


class VirtualSection(Section):
    pass


class AwesomeNavigation:
    def __init__(
        self,
        items: List[NavigationItem],
        options: Options,
        docs_dir: str,
        explicit_sections: Set[Section],
    ):
        self.options = options
        self.Allpages = []
        self.maximum_file_homepage = int(float(options.maximum_file_homepage))
        self.maximum_days_ahead = int(float(options.maximum_days_ahead))
        self.ai_report_path_prefix = options.ai_report_path_prefix
        self.ai_report_recent_limit = int(float(options.ai_report_recent_limit))
        self.ai_report_pin_to_top = options.ai_report_pin_to_top
        self.explicit_sections = explicit_sections

        self.meta = NavigationMeta(items, options, docs_dir, explicit_sections)

        if self.meta.root.title is not None:
            warnings.warn(TitleInRootHasNoEffect(self.options.filename))

        if self.meta.root.hide is not None:
            warnings.warn(HideInRootHasNoEffect(self.options.filename))

        self.items = self._process_children(items, self.options.collapse_single_pages, self.meta.root)

    def _process_children(self, children: List[NavigationItem], collapse: bool, meta: Meta) -> List[NavigationItem]:
        self._order(children, meta)
        children = self._nav(children, meta)

        result = []

        for item in children:
            if isinstance(item, Section) and not isinstance(item, VirtualSection):
                item = self._process_section(item, collapse)
                if item is None:
                    continue
            result.append(item)

        return result

    def _order(self, items: List[NavigationItem], meta: Meta):
        order, sort_type = meta.order, meta.sort_type
        if order is None and sort_type is None:
            return
        key = lambda i: basename(self._get_item_path(i))
        if sort_type == Meta.SORT_NATURAL:
            key = natsort_keygen(key)
        items.sort(key=key, reverse=order == Meta.ORDER_DESC)

    def _nav(self, items: List[NavigationItem], meta: Meta) -> List[NavigationItem]:
        if meta.nav is None:
            return items

        items_by_basename = {basename(self._get_item_path(item)): item for item in items}

        used_items = []
        rest_items = RestItemList()

        def _make_nav_rec(meta_nav: List[MetaNavItem]) -> List[Union[NavigationItem, MetaNavRestItem]]:
            result = []
            for meta_item in meta_nav:
                if isinstance(meta_item, MetaNavRestItem):
                    rest_items.append(meta_item)
                    result.append(meta_item)

                elif isinstance(meta_item.value, list):
                    result.append(VirtualSection(meta_item.title, children=_make_nav_rec(meta_item.value)))

                elif meta_item.value in items_by_basename:
                    item = items_by_basename[meta_item.value]
                    if meta_item.title is not None:
                        item.title = meta_item.title
                    result.append(item)
                    used_items.append(item)

                elif meta_item.title is not None:
                    result.append(Link(meta_item.title, meta_item.value))

                else:
                    warning = NavEntryNotFound(meta_item.value, meta.path)
                    if self.options.strict:
                        raise warning
                    else:
                        warnings.warn(warning)
            return result

        result = _make_nav_rec(meta.nav)

        if rest_items:
            rest = {rest_item: [] for rest_item in rest_items}

            for item in items:
                if item not in used_items:
                    path = basename(self._get_item_path(item))
                    for rest_item in rest_items:
                        if rest_item.matches(path):
                            rest[rest_item].append(item)
                            break

            def _expand_rest_rec(result: List[Union[NavigationItem, MetaNavRestItem]]):
                for index, item in enumerate(result):
                    if isinstance(item, MetaNavRestItem):
                        result[index : index + 1] = rest[item]
                    elif isinstance(item, Section):
                        if item.children:
                            _expand_rest_rec(item.children)

            _expand_rest_rec(result)

        return result

    def _process_section(self, section: Section, collapse_recursive: bool) -> Optional[NavigationItem]:
        meta = self.meta.sections[section]

        if meta.hide is True:
            return None

        if meta.collapse_single_pages is not None:
            collapse_recursive = meta.collapse_single_pages

        self._set_title(section, meta)

        section.children = self._process_children(section.children, collapse_recursive, meta)

        if section in self.explicit_sections:
            return section

        if not section.children:
            return None

        return self._collapse(section, meta.collapse, collapse_recursive)

    def _is_ai_report_page(self, page: Page) -> bool:
        """Return True only when prefix is non-empty and page.file.src_path starts with prefix."""
        if not self.ai_report_path_prefix:
            return False
        return page.file.src_path.startswith(self.ai_report_path_prefix)

    def _safe_parse_time(self, page: Page) -> Optional[datetime]:
        """Parse page.meta.get('time') in YYYYMMDD format. Return None on invalid/missing time."""
        try:
            time_val = page.meta.get("time")
            if time_val is None:
                return None
            time_str = str(time_val).strip()
            if len(time_str) < 8:
                return None
            year = int(time_str[0:4])
            month = int(time_str[4:6])
            day = int(time_str[6:8])
            return datetime(year, month, day)
        except (ValueError, TypeError, IndexError):
            return None

    def _get_item_path(self, item: NavigationItem) -> Optional[str]:
        if isinstance(item, Section):
            return dirname(self.meta.sections[item].path)
        elif isinstance(item, Page):
            return item.file.abs_src_path

    @staticmethod
    def _set_title(section: Section, meta: Meta):
        if meta.title is not None:
            section.title = meta.title

    @staticmethod
    def _collapse(section: Section, collapse: Optional[bool], collapse_recursive: bool) -> NavigationItem:
        if collapse is None:
            collapse = collapse_recursive

        if collapse and len(section.children) == 1:
            return section.children[0]
        return section

    def _get_meta(self, page_):
        with io.open(page_.file.abs_src_path, 'r', encoding='utf-8-sig', errors='strict') as f:
            source = f.read()
        
        _, page_.meta = mkdocs_meta.get_data(source)

    def to_mkdocs(self) -> MkDocsNavigation:
        pages = get_by_type(self.items, Page)
        _add_previous_and_next_links(pages)
        _add_parent_links(self.items)

        date_today = datetime.today()
        sentinel_days = 999999

        # Compute recency (days ago) for each page
        page_recency = []
        for page in pages:
            self._get_meta(page)
            parsed = self._safe_parse_time(page)
            if parsed is not None:
                delta = date_today - parsed
                total_days = delta.total_seconds() / 86400
            else:
                total_days = sentinel_days
            page_recency.append(total_days)

        # Sort indices by recency (ascending = newest first)
        sorted_indices = sorted(range(len(pages)), key=lambda i: page_recency[i])

        # Build page_list and assign shown_in_homepage
        page_list = []
        count_shown = 0
        count_ai_report_shown = 0
        ai_prefix_set = bool(self.ai_report_path_prefix)
        ai_limit = self.ai_report_recent_limit

        for index in sorted_indices:
            page = pages[index]
            recency_days = page_recency[index]

            # Homepage always first in page_list
            if page.is_homepage:
                page_list.insert(0, page)
            else:
                page_list.append(page)

            # shown_in_homepage: within recency window and under limits
            if recency_days < self.maximum_days_ahead and count_shown < self.maximum_file_homepage:
                is_ai = self._is_ai_report_page(page)
                if ai_prefix_set and ai_limit > 0 and is_ai:
                    if count_ai_report_shown < ai_limit:
                        page.shown_in_homepage = True
                        count_shown += 1
                        count_ai_report_shown += 1
                    else:
                        page.shown_in_homepage = False
                else:
                    page.shown_in_homepage = True
                    count_shown += 1
                    if is_ai:
                        count_ai_report_shown += 1
            else:
                page.shown_in_homepage = False

        # Optional: reorder page_list when ai_report_pin_to_top is enabled
        if self.ai_report_pin_to_top and ai_prefix_set and len(page_list) > 1:
            homepage_page = None
            if page_list[0].is_homepage:
                homepage_page = page_list.pop(0)
            ai_pages = [p for p in page_list if self._is_ai_report_page(p)]
            non_ai_pages = [p for p in page_list if not self._is_ai_report_page(p)]
            # AI pages by recency (newest first), then non-AI preserving relative order
            ai_with_recency = [(p, page_recency[pages.index(p)]) for p in ai_pages]
            ai_with_recency.sort(key=lambda x: x[1])
            ai_sorted = [p for p, _ in ai_with_recency]
            page_list = ai_sorted + non_ai_pages
            if homepage_page is not None:
                page_list.insert(0, homepage_page)

        return MkDocsNavigation(self.items, page_list)


class NavigationMeta:
    def __init__(
        self,
        items: List[NavigationItem],
        options: Options,
        docs_dir: str,
        explicit_sections: Set[Section],
    ):
        self.options = options
        self.sections = {}
        self.docs_dir = docs_dir
        self.explicit_sections = explicit_sections

        root_path = self._gather_metadata(items)
        self.root = Meta.try_load_from(join_paths(root_path, self.options.filename))

    def _gather_metadata(self, items: List[NavigationItem]) -> Optional[str]:
        paths = []
        for item in items:
            if isinstance(item, Page):
                if Path(self.docs_dir) in Path(item.file.abs_src_path).parents:
                    paths.append(item.file.abs_src_path)
            elif isinstance(item, Section):
                section_dir = self._gather_metadata(item.children)
                if item in self.explicit_sections:
                    self.sections[item] = Meta()
                else:
                    if section_dir is not None:
                        paths.append(section_dir)
                    self.sections[item] = Meta.try_load_from(join_paths(section_dir, self.options.filename))

        return self._common_dirname(paths)

    @staticmethod
    def _common_dirname(paths: List[Optional[str]]) -> Optional[str]:
        if paths:
            dirnames = [dirname(path) for path in paths]
            if len(set(dirnames)) == 1:
                return dirnames[0]


# Copy of mkdocs.structure.nav._get_by_type with fix for nested sections
# PR: https://github.com/mkdocs/mkdocs/pull/2203
def get_by_type(nav, T):
    ret = []
    for item in nav:
        if isinstance(item, T):
            ret.append(item)
        if item.children:
            ret.extend(get_by_type(item.children, T))
    return ret
