from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts_app.urls')),
    path('api/wallet/', include('wallet.urls')),
    path('api/goals/', include('goals.urls')),
    path('api/streaks/', include('streaks.urls')),
    path('api/social/', include('social.urls')),
    path('api/expenses/', include('expenses.urls')),
    path('api/splits/', include('splits.urls')),
]

handler404 = 'config.error_views.handler404'
handler403 = 'config.error_views.handler403'
handler500 = 'config.error_views.handler500'
