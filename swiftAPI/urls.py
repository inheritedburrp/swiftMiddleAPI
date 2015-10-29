"""swiftAPI URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^index/', views.index, name='index'),
    url(r'^authenticate/', views.authenticate, name='authenticate'),
    url(r'^save/', views.save, name='save'),
    url(r'^get/(?P<account>([a-zA-Z0-9_]+))/(?P<container>\w+)/(?P<object_name>([\w\s\d\._-]+))/',
        views.get_obj, name='get'),
]