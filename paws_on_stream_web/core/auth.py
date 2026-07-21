from django.contrib.auth.mixins import UserPassesTestMixin


class StaffRequiredMixin(UserPassesTestMixin):
    login_url = "/auth/login/"
    raise_exception = False

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def dispatch(self, request, *args, **kwargs):
        return UserPassesTestMixin.dispatch(self, request, *args, **kwargs)


class StrictStaffRequiredMixin(StaffRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        return UserPassesTestMixin.dispatch(self, request, *args, **kwargs)


class AdminRequiredMixin(UserPassesTestMixin):
    """Restrict dashboard administration to authenticated administrators."""

    login_url = "/auth/login/"
    raise_exception = True

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser
