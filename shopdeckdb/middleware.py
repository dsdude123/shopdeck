'''
General purpose Middleware for both the eShop & Web UI servers
'''
import os
from shopdeck import settings
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.contrib.auth import get_user_model, login

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")

class AdminAutologinMiddleware(object):
	'''
	Grants passwordless superuser access to /admin/. There is intentionally no
	login system for the admin: any request under /admin/ is auto-authenticated
	as a superuser (created on demand). This is LAN-only by design — keep this
	server off the public Internet.
	'''
	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		if request.path.startswith("/admin") and not request.user.is_authenticated:
			User = get_user_model()
			user, _ = User.objects.get_or_create(
				username=ADMIN_USERNAME,
				defaults={"is_staff": True, "is_superuser": True, "is_active": True},
			)
			if not (user.is_staff and user.is_superuser and user.is_active):
				user.is_staff = user.is_superuser = user.is_active = True
				user.save(update_fields=["is_staff", "is_superuser", "is_active"])
			login(request, user, backend="django.contrib.auth.backends.ModelBackend")
			request.user = user
		return self.get_response(request)

class ShopMiddleware(object):
	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		if settings.IN_MAINTENANCE:
			if request.path.startswith("/ninja/ws") or request.path.startswith("/samurai/ws"):
				return JsonResponse({"error": {"code": "6516", "message": settings.MAINTENANCE_MSG}}, status=400)
			else:
				return HttpResponse("Maintenance is in progress. Please come back later.", status=503)
		if not request.path.startswith("/admin") and request.user.is_authenticated and request.user.linked_ds == None:
			return HttpResponse("Your account is misconfigured. Contact an admin. It is not currently usable.")
		if request.user.is_authenticated and request.user.linked_ds != None:
			if request.user.linked_ds.is_terminated:
				return HttpResponse("Your account has been terminated.")
		if not request.user.is_authenticated and not request.path.startswith("/ninja") and not request.path.startswith("/samurai") and not request.path.startswith("/login") and not request.path.startswith("/signup") and not request.path == "/":
			return HttpResponseRedirect("/")
		response = self.get_response(request)
		return response
