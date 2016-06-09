from django.utils.encoding import python_2_unicode_compatible
from jsontableschema.model import SchemaModel
from openpyxl import Workbook
from openpyxl.styles import Font

from upload.utils_openpyxl import write_values, is_blank_value

COLUMN_HEADER_FONT = Font(bold=True)


def write_headers(dataset, ws):
    schema = dataset.schema
    headers = [field.get('name', 'No name') for field in schema.get('fields', [])]
    write_values(ws, 1, 1, headers, direction='right', font=COLUMN_HEADER_FONT)


def to_template_workbook(dataset):
    wb = Workbook()
    ws = wb.active
    ws.title = dataset.name
    write_headers(dataset, wb.active)
    return wb


@python_2_unicode_compatible
class SchemaField:
    """
    Utility class for a field in a schema.
    It uses the schema types of
    https://github.com/frictionlessdata/jsontableschema-py#types
    for validation.
    """

    def __init__(self, data):
        self.data = data
        self.name = data['name']  # We want to throw an exception if there is no name
        # use of jsontableschema.types to help constraint validation
        self.type = SchemaModel._type_map()[data.get('type')](data)

    @property
    def column_name(self):
        return self.name

    @property
    def constraints(self):
        return self.data.get('constraints', {})

    @property
    def required(self):
        return self.constraints.get('required', False)

    def cast(self, value):
        """
        Returns o native Python object of the expected format. Will throw an exception
        if the value doesn't complies with any constraints. See for details:
        https://github.com/frictionlessdata/jsontableschema-py#types
        This method is mainly a helper for the validation_error
        :param value:
        :return:
        """
        if is_blank_value(value):
            # must do that because an empty string is considered as valid even if required by the StringType
            value = None
        if isinstance(value, basestring):
            # the StringType accepts only unicode
            value = unicode(value)
        return self.type.cast(value)

    def validation_error(self, value):
        """
        Try to cast and catch the exception if any
        :param value:
        :return: None if value is valid or an error message string
        """
        error = None
        try:
            self.cast(value)
        except Exception as e:
            error = e.message
        return error

    def __str__(self):
        return '{}'.format(self.name)


@python_2_unicode_compatible
class SchemaForeignKey:
    """
    A utility class for foreign key in schema
    """

    def __init__(self, data):
        self.data = data

    def __str__(self):
        return 'Foreign Key {}'.format(self.data)

    @staticmethod
    def _as_list(value):
        if isinstance(value, list):
            return value
        elif isinstance(value, basestring):
            return [value]
        else:
            return list(value)

    @property
    def fields(self):
        return self._as_list(self.data.get('fields', []))

    @property
    def data_field(self):
        return self.fields[0] if self.fields else None

    @property
    def reference(self):
        return self.data.get('reference', {})

    @property
    def reference_fields(self):
        return self._as_list(self.reference.get('fields', []))

    @property
    def reference_resource(self):
        return self.reference.get('resource')

    @property
    def model(self):
        return self.reference_resource

    @property
    def model_field(self):
        return self.reference_fields[0] if self.reference_fields else None


class Schema:
    """
    A utility class for schema.
    It uses internally an instance SchemaModel of the frictionless jsontableschema for help.
    https://github.com/frictionlessdata/jsontableschema-py#model
    """

    def __init__(self, schema):
        self.data = schema
        self.schema_model = SchemaModel(schema)
        self.fields = [SchemaField(f) for f in self.schema_model.fields]
        self.foreign_keys = [SchemaForeignKey(fk) for fk in
                             self.schema_model.foreignKeys] if self.schema_model.foreignKeys else []

    @property
    def headers(self):
        return self.field_names

    @property
    def field_names(self):
        return [f.name for f in self.fields]

    def get_field_by_mame(self, name):
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def field_validation_error(self, field_name, value):
        field = self.get_field_by_mame(field_name)
        if field is not None:
            return field.validation_error(value)
        else:
            raise Exception("The field '{}' doesn't exists in the schema. Should be one of {}"
                            .format(field_name, self.field_names))

    def is_field_valid(self, field_name, value):
        return self.field_validation_error(field_name, value) is None

    def validate_row(self, row):
        """
        The row must be a dictionary or a list of key value
        :param row:
        :return: return a dictionary with an error added to the field
        {
            field_name: {
                value: value (as given)
                error: None or error message
        }
        """
        row = dict(row)
        result = {}
        for field_name, value in row.items():
            error = self.field_validation_error(field_name, value)
            result[field_name] = {
                'value': value,
                'error': error
            }
        return result

    def rows_validator(self, rows):
        for row in rows:
            yield self.validate_row(row)

    def get_error_fields(self, row):
        """
        Return the field that does not validate
        :param row: a key value dict or tuple
        :return: [(field_name, {'value':value, 'error':error_string}]
        """
        validated_row = self.validate_row(row)
        errors = []
        for field, data in validated_row.items():
            if data.get('error'):
                errors.append((field, data))
        return errors

    def is_row_valid(self, row):
        return len(self.get_error_fields(row)) == 0

    def is_all_valid(self, rows):
        for row in rows:
            if not self.is_row_valid(row):
                return False
        return True

    def has_fk_for_model(self, model_name):
        return self.get_fk_for_model(model_name) is not None

    def get_fk_for_model(self, model_name):
        for fk in self.foreign_keys:
            if fk.model == model_name:
                return fk
        return None


class Exporter:
    def __init__(self, dataset, records=None):
        self.ds = dataset
        self.schema = Schema(dataset)
        self.headers = self.schema.headers
        self.warnings = []
        self.errors = []
        self.records = records if records else []

    def row_it(self):
        for record in self.records:
            row = []
            for field in self.schema.field_names:
                row.append(unicode(record.get(field, '')))
            yield row

    def to_csv(self):
        rows = list()
        rows.append(self.headers)
        rows += list(self.row_it())
        return rows

    def to_worksheet(self, ws):
        ws.title = self.ds.name
        write_values(ws, 1, 1, self.headers, direction='right', font=COLUMN_HEADER_FONT)
        row_count = 1
        for row in self.row_it():
            row_count += 1
            write_values(ws, row_count, 1, row)
        return ws

    def to_workbook(self):
        wb = Workbook()
        self.to_worksheet(wb.active)
        return wb