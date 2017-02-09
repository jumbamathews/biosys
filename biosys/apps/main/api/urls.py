from __future__ import absolute_import, unicode_literals, print_function, division

from django.conf.urls import url
from rest_framework import routers

from main.api import views as main_views

router = routers.DefaultRouter()
router.register(r'users?', main_views.UserViewSet, 'user')
router.register(r'projects?', main_views.ProjectViewSet, 'project')
router.register(r'sites?', main_views.SiteViewSet, 'site')
router.register(r'datasets?', main_views.DatasetViewSet, 'dataset')
router.register(r'records?', main_views.RecordViewSet, 'record')

url_patterns = [
    url(r'projects?/(?P<pk>\d+)/sites/?', main_views.ProjectSitesView.as_view(), name='project-sites'),  # bulk sites
    url(r'projects?/(?P<pk>\d+)/upload-sites/?', main_views.ProjectSitesUploadView.as_view()
        , name='upload-sites'),  # file upload for sites
    url(r'datasets?/(?P<pk>\d+)/data/?', main_views.DatasetDataView.as_view(), name='dataset-data'),
    # upload data files
    url(r'datasets?/(?P<pk>\d+)/upload-records/?', main_views.DatasetUploadRecordsView.as_view(),
        name='dataset-upload'),
    url(r'statistics/?', main_views.StatisticsView.as_view(), name="statistics"),
    url(r'whoami/?', main_views.WhoamiView.as_view(), name="whoami"),
    url(r'species/?', main_views.SpeciesView.as_view(), name="species"),
    url(r'logout/?', main_views.LogoutView.as_view(), name="logout"),
]

urls = router.urls + url_patterns