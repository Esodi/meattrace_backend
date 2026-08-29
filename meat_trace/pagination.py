from rest_framework.pagination import PageNumberPagination


class LargeResultsSetPagination(PageNumberPagination):
    """Bounds response size for endpoints that were previously unpaginated
    (e.g. AnimalViewSet, SlaughterPartViewSet). Default page size matches the
    page_size the Flutter client already sends so existing callers keep
    getting effectively the full list, while very large histories no longer
    blow up the response."""
    page_size = 1000
    page_size_query_param = 'page_size'
    max_page_size = 2000
