# -*- coding: utf-8 -*-
import urllib

from django.contrib import admin
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.conf.urls.defaults import patterns, url
from django.core.urlresolvers import reverse
from django.utils import simplejson as json
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import user_passes_test
from django.views.decorators.csrf import csrf_exempt

class MultiUploadAdmin(admin.ModelAdmin):
    class Media:
        js = (
            'jquery/jquery.1.8.0.min.js',
            'jquery/jquery_fix_csrf.js',
            'jquery/jquery.ui.widget.js',
            'jquery/tmpl.min.js',
            'jquery/canvas-to-blob.min.js',
            'jquery/load-image.min.js',
            'jquery/jquery.iframe-transport.js',
            'jquery/jquery.fileupload.js',
            'jquery/jquery.fileupload-fp.js',
            'jquery/jquery.fileupload-ui.js',
        )
        css = {
            'all': ['css/jquery-ui.css',
                    'css/jquery.fileupload-ui.css',
                    'css/multiupload.css',
                    ],
        }
    change_form_template = 'multiupload/change_form.html'
    change_list_template = 'multiupload/change_list.html'
    multiupload_template = 'multiupload/upload.html'
    multiupload_list = True
    multiupload_form = True
    # integer in bytes
    multiupload_maxfilesize = 3 * 2 ** 20 # 3 Mb
    multiupload_minfilesize = 0
    # tuple with mimetype accepted
    multiupload_acceptedformats = ( "image/jpeg",
                                    "image/pjpeg",
                                    "image/png",)

    @property
    def upload_options(self):
        return {
            "maxfilesize": self.multiupload_maxfilesize,
            "minfilesize": self.multiupload_minfilesize,
            "acceptedformats": self.multiupload_acceptedformats,
          }

    def render_change_form(self, request, context, *args, **kwargs):
        context.update({
            'multiupload_form': self.multiupload_form,
        })
        if self.multiupload_form:
            if 'object_id' in context:
                object_id = context['object_id']
                context.update({
                    'multiupload_form_url': reverse(
                        'admin:%s' % self.get_multiupload_form_view_name(),
                         args=[object_id,]),
                })
        return super(MultiUploadAdmin, self).render_change_form(
                request, context, *args, **kwargs)

    def changelist_view(self, request, extra_context=None):
        pop = request.REQUEST.get('pop')
        extra_context = extra_context or {}
        extra_context.update({
                'multiupload_list': self.multiupload_list,
            })
        if self.multiupload_list:
            url = reverse('admin:%s' % self.get_multiupload_list_view_name())
            if pop:
                url += '?pop=1'
            extra_context.update({
                'multiupload_list_url': url,
            })
        return super(MultiUploadAdmin, self).changelist_view(
            request, extra_context)

    def get_multiupload_list_view_name(self):
        module_name = self.model._meta.module_name
        return '%s_multiupload_list' % module_name

    def get_multiupload_form_view_name(self):
        module_name = self.model._meta.module_name
        return '%s_multiupload_form' % module_name

    def get_urls(self, *args, **kwargs):
        multi_urls = patterns('')
        if self.multiupload_list:
            multi_urls += patterns('',
                url(r'^multiupload/$',
                    self.admin_site.admin_view(self.admin_upload_view),
                    name=self.get_multiupload_list_view_name())
            )
        if self.multiupload_form:
            multi_urls += patterns('',
                url(r'^(?P<id>\d+)/multiupload/$',
                    self.admin_site.admin_view(self.admin_upload_view),
                    name=self.get_multiupload_form_view_name()),
            )
        return multi_urls + super(MultiUploadAdmin, self
            ).get_urls(*args, **kwargs)

    def process_uploaded_file(self, uploaded, object, **kwargs):
        '''
        Process uploaded file
        Parameters:
            uploaded: File that was uploaded
            object: parent object where multiupload is
            **kwargs: is request.POST
        Must return a dict with:
        return {
            'thumbnail_url': 'full_path_to_thumb.png',
            'url': 'full_file_URL.png',
            'file_id': 'id of created file',

            # optionals
            "name": "filename",
            "size": "filesize",
            "type": "file content type",
            "delete_type": "POST",
            "error" = 'Error message or jQueryFileUpload Error code'
        }
        '''
        return {}

    def delete_file(self, pk, request):
        '''
        Function to delete a file.
        '''
        obj = get_object_or_404(self.queryset(request), pk=pk)
        obj.delete()

    @csrf_exempt
    # @user_passes_test(lambda u: u.is_staff)
    def admin_upload_view(self, request, id=None):
        if id:
            object = self.get_object(request, id)
        else:
            object = None
        if request.method == 'POST':    # POST data
            if not ("f" in request.GET.keys()): # upload file
                if not request.FILES:
                    return HttpResponseBadRequest('Must upload a file')

                # get the uploaded file
                files = request.FILES.getlist(u'files[]')
                resp = []

                for f in files:
                    error = False

                    # file size
                    if f.size > self.upload_options["maxfilesize"]:
                        error = "maxFileSize"
                    if f.size < self.upload_options["minfilesize"]:
                        error = "minFileSize"
                        # allowed file type
                    if f.content_type not in self.upload_options["acceptedformats"]:
                        error = "acceptFileTypes"

                    # the response data which will be returned to
                    # the uploader as json
                    response_data = {
                        "name": f.name,
                        "size": f.size,
                        "type": f.content_type,
                        "delete_type": "POST",
                    }

                    # if there was an error, add error message 
                    # to response_data and return
                    if error:
                        # append error message
                        response_data["error"] = error
                        # generate json
                    else:
                        while 1:
                            chunk = f.file.read(10000)
                            if not chunk:
                                break
                        f.file.seek(0)

                        # Manipulate file.
                        data = self.process_uploaded_file(f, object,
                                        request)

                        assert 'id' in data, 'Must return id in data'
                        response_data.update(data)
                        response_data['delete_url'] = request.path + "?"\
                            + urllib.urlencode({'f': data['id']})

                    resp.append(response_data)

                # generate the json data
                response_data = json.dumps(resp)
                # response type
                response_type = "application/json"

                # QUIRK HERE
                # in jQuey uploader, when it falls back to uploading using iFrames
                # the response content type has to be text/html
                # if json will be send, error will occur
                # if iframe is sending the request, it's headers are
                # a little different compared
                # to the jQuery ajax request
                # they have different set of HTTP_ACCEPT values
                # so if the text/html is present, file was uploaded
                # using jFrame because
                # that value is not in the set when uploaded by XHR
                if "text/html" in request.META["HTTP_ACCEPT"]:
                    response_type = "text/html"
                response_type = "text/html"

                # return the data to the uploading plugin
                return HttpResponse(response_data, mimetype=response_type)

            else: # file has to be deleted
                # get the file path by getting it from the query
                # (e.g. '?f=filename.here')
                self.delete_file(request.GET["f"], request)

                # generate true json result
                # in this case is it a json True value
                # if true is not returned, the file will not be
                # removed from the upload queue
                response_data = json.dumps(True)

                # return the result data
                # here it always has to be json
                return HttpResponse(response_data, mimetype="application/json")

        else: #GET
            context = {
                # these two are necessary to generate the jQuery templates
                # they have to be included here since they conflict
                #  with django template system
                "open_tv": u'{{',
                "close_tv": u'}}',
                # some of the parameters to be checked by javascript
                "maxfilesize": self.upload_options["maxfilesize"],
                "minfilesize": self.upload_options["minfilesize"],
                # django admin parameters
                "object": object,
                'media': self.media,
                'opts': self.model._meta,
                'change': False,
                'is_popup': request.GET.has_key('pop'),
                'add': True,
                'app_label': self.model._meta.app_label,
                'save_as': 'teste',
                'has_delete_permission': False,
                'has_add_permission': False,
                'has_change_permission': False,
            }

            return render(request,
                self.multiupload_template,
                context,
                )
