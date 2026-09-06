"""Custom JSON error handlers for a pure-API backend (no HTML templates needed)."""
from django.http import JsonResponse


def handler404(request, exception=None):
    return JsonResponse({'detail': 'The requested resource was not found.'}, status=404)


def handler403(request, exception=None):
    return JsonResponse({'detail': 'You do not have permission to perform this action.'}, status=403)


def handler500(request):
    return JsonResponse({'detail': 'An unexpected server error occurred. Please try again later.'}, status=500)
