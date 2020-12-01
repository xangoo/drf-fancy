from ast import literal_eval

from getter import get_setting, get_model
from rest_framework import viewsets, filters


class FancyViewSet(viewsets.ModelViewSet):
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]

    def __init__(self, **kwargs):
        if hasattr(self.serializer_class, 'Meta') and hasattr(self.serializer_class.Meta, 'fields'):
            self.ordering_fields = self.serializer_class.Meta.fields
            self.search_fields = self.serializer_class.Meta.fields

        super().__init__(**kwargs)

    # noinspection PyProtectedMember
    @property
    def credential(self):
        if hasattr(self.request._request, 'credential'):
            return self.request._request.credential
        return None

    def get_queryset(self):
        type_casting = get_setting('FANCY', 'TYPE_CASTING')

        params = {}
        for param in self.request.query_params:
            # To avoid confusion we start our filter parameters with "__"
            if not param.startswith('__'):
                continue
            key = param[2:]

            # Django "filter" dose not support numerical conversion for JSON fields. We convert all params ourself
            value = self.request.query_params[param]
            if param.endswith('__in'):  # When we use "in" we have to convert our value into a list
                value = literal_eval(value)
                if not isinstance(value, tuple):
                    value = (value,)
                params[key] = value
            elif type_casting:  # Django dose not convert JSON numeric value automatically
                try:
                    if '.' in value:
                        params[key] = float(value)
                    else:
                        params[key] = int(value)
                except ValueError:
                    params[key] = value
            else:  # We trust Django and do not check for correct values
                params[key] = value

        return self.serializer_class.Meta.model.objects.filter(**params)


class FancySelfViewSet(FancyViewSet):
    self_field: str
    self_model: tuple

    def get_queryset(self):
        if not self.credential:
            raise KeyError('No credential found')

        return self.queryset.filter(**{self.self_field: self.credential.id})

    def create(self, request, *args, **kwargs):
        if not self.credential:
            raise KeyError('No credential found')

        if hasattr(self, 'self_field') and '__' not in self.self_field:
            request.data[self.self_field] = self.credential.id

        response = super(FancySelfViewSet, self).create(request, *args, **kwargs)

        if hasattr(self, 'self_model'):
            model_name, left, right = self.self_model
            model_class = get_model(model_name)
            args = {left: response.data['id'], right: self.credential.id}
            instant = model_class(**args)
            instant.save()

        return response
