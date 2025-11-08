from django.urls import path
from . import views


# Admin template routes (separate file so the app can avoid loading
# admin UI in environments that don't need it). To enable these routes,
# include them from your project URLConf, for example:
#     path('site-admin/', include('meat_trace.admin_urls'))
# or mount them under another prefix you prefer.

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('users/', views.admin_users, name='admin_users'),
    path('supply-chain/', views.admin_supply_chain, name='admin_supply_chain'),
    path('performance/', views.admin_performance, name='admin_performance'),
    path('compliance/', views.admin_compliance, name='admin_compliance'),
    path('system-health/', views.admin_system_health, name='admin_system_health'),
]
