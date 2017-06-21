from __future__ import absolute_import, unicode_literals, print_function, division

import json
import logging
import re

from dateutil.parser import parse as date_parse
from django.contrib.gis.geos import Point
from django.utils import six
from django.utils.encoding import python_2_unicode_compatible
from future.utils import raise_with_traceback
from jsontableschema.exceptions import InvalidDateType
from jsontableschema.model import SchemaModel, types
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.writer.write_only import WriteOnlyCell

from main.constants import MODEL_SRID, SUPPORTED_DATUMS, get_datum_srid, is_supported_datum, get_australian_zone_srid, \
    is_projected_srid

COLUMN_HEADER_FONT = Font(bold=True)
YYYY_MM_DD_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2}')

logger = logging.getLogger(__name__)


def is_blank_value(value):
    return value is None or is_empty_string(value)


def is_empty_string(value):
    return isinstance(value, six.string_types) and len(value.strip()) == 0


class ObservationSchemaError(Exception):
    # don't  extend InvalidSchemaError (problem with message not showing in the str method)
    pass


class SpeciesObservationSchemaError(Exception):
    pass


class GeometrySchemaError(Exception):
    pass


class InvalidDatumError(Exception):
    pass


class FieldSchemaError(Exception):
    pass


def parse_datetime_day_first(value):
    """
    use the dateutil.parse() to parse a date/datetime with the date first (dd/mm/yyyy) (not month first mm/dd/yyyy)
    in case of ambiguity
    :param value:
    :return:
    """
    # there's a 'bug' in dateutil.parser.parse (2.5.3). If you are using
    # dayfirst=True. It will parse YYYY-MM-DD as YYYY-DD-MM !!
    # https://github.com/dateutil/dateutil/issues/268
    dayfirst = not YYYY_MM_DD_REGEX.match(value)
    return date_parse(value, dayfirst=dayfirst)


class DayFirstDateType(types.DateType):
    """
    Extend the jsontableschema DateType which use the mm/dd/yyyy date model for the 'any' format
    to use dd/mm/yyyy
    """

    def cast_any(self, value, fmt=None):
        if isinstance(value, self.python_type):
            return value
        try:
            return parse_datetime_day_first(value).date()
        except (TypeError, ValueError) as e:
            raise_with_traceback(InvalidDateType(e))


class DayFirstDateTimeType(types.DateTimeType):
    """
    Extend the jsontableschema DateType which use the mm/dd/yyyy date model for the 'any' format
    to use dd/mm/yyyy
    """

    def cast_any(self, value, fmt=None):
        if isinstance(value, self.python_type):
            return value
        try:
            return parse_datetime_day_first(value)
        except (TypeError, ValueError) as e:
            raise_with_traceback(InvalidDateType(e))


class NotBlankStringType(types.StringType):
    """
    The default StringType accepts empty string when required = True
    """
    null_values = ['null', 'none', 'nil', 'nan', '-', '']


@python_2_unicode_compatible
class BiosysSchema:
    """
    The utility class for the biosys data within a schema field

    {
      name: "...."
      constraints: ....
      biosys: {
                type: [observationDate]
              }
    }
    """
    OBSERVATION_DATE_TYPE_NAME = 'observationDate'
    LATITUDE_TYPE_NAME = 'latitude'
    LONGITUDE_TYPE_NAME = 'longitude'
    EASTING_TYPE_NAME = 'easting'
    NORTHING_TYPE_NAME = 'northing'
    DATUM_TYPE_NAME = 'datum'
    ZONE_TYPE_NAME = 'zone'
    SPECIES_NAME_TYPE_NAME = 'speciesName'
    SPECIES_NAME_ID_TYPE_NAME = 'speciesNameId'
    SITE_CODE_TYPE_NAME = 'siteCode'

    BIOSYS_TYPE_MAP = {
        OBSERVATION_DATE_TYPE_NAME: DayFirstDateType,
    }

    def __init__(self, data):
        self.data = data or {}

    # implement some dict like methods
    def __getitem__(self, item):
        return self.data.__getitem__(item)

    def __str__(self):
        return "BiosysSchema: {}".format(self.data)

    @property
    def type(self):
        return self.get('type')

    def get(self, k, d=None):
        return self.data.get(k, d)

    def is_observation_date(self):
        return self.type == self.OBSERVATION_DATE_TYPE_NAME

    def is_latitude(self):
        return self.type == self.LATITUDE_TYPE_NAME

    def is_longitude(self):
        return self.type == self.LONGITUDE_TYPE_NAME

    def is_easting(self):
        return self.type == self.EASTING_TYPE_NAME

    def is_northing(self):
        return self.type == self.NORTHING_TYPE_NAME

    def is_datum(self):
        return self.type == self.DATUM_TYPE_NAME

    def is_zone(self):
        return self.type == self.ZONE_TYPE_NAME

    def is_species_name(self):
        return self.type == self.SPECIES_NAME_TYPE_NAME

    def is_species_name_id(self):
        return self.type == self.SPECIES_NAME_ID_TYPE_NAME


@python_2_unicode_compatible
class SchemaField:
    """
    Utility class for a field in a schema.
    It uses the schema types of
    https://github.com/frictionlessdata/jsontableschema-py#types
    for validation.
    """
    # For most of the type we use the jsontableschema ones
    BASE_TYPE_MAP = SchemaModel._type_map()
    # except for the date we use our custom one.
    BASE_TYPE_MAP['date'] = DayFirstDateType
    BASE_TYPE_MAP['datetime'] = DayFirstDateTimeType
    BASE_TYPE_MAP['string'] = NotBlankStringType

    BIOSYS_TYPE_MAP = {
    }

    def __init__(self, data):
        self.data = data
        self.name = self.data.get('name')
        # We want to throw an exception if there is no name
        if not self.name:
            raise FieldSchemaError("A field without a name: {}".format(json.dumps(data)))
        # biosys specific
        self.biosys = BiosysSchema(self.data.get('biosys'))
        # set the type: biosys type as precedence
        type_class = self.BIOSYS_TYPE_MAP.get(self.biosys.type) or self.BASE_TYPE_MAP.get(self.data.get('type'))
        self.type = type_class(self.data)
        self.constraints = SchemaConstraints(self.data.get('constraints', {}))

    # implement some dict like methods
    def __getitem__(self, item):
        return self.data.__getitem__(item)

    def get(self, k, d=None):
        return self.data.get(k, d)

    @property
    def title(self):
        return self.data.get('title')

    @property
    def column_name(self):
        return self.name

    @property
    def required(self):
        return self.constraints.required

    @property
    def aliases(self):
        return self.data['aliases'] if 'aliases' in self.data else []

    def has_alias(self, name, icase=False):
        for alias in self.aliases:
            if (alias == name) or (icase and alias.lower() == name.lower()):
                return True
        return False

    def has_name_or_alias(self, name, alias, icase=False):
        """
        Test is the field has a name name or an alias alias
        :param name:
        :param alias:
        :param icase:
        :return:
        """
        has_name = (self.name == name) or (icase and self.name.lower() == name.lower())
        return has_name or self.has_alias(alias, icase=icase)

    def cast(self, value):
        """
        Returns o native Python object of the expected format. Will throw an exception
        if the value doesn't complies with any constraints. See for details:
        https://github.com/frictionlessdata/jsontableschema-py#types
        This method is mainly a helper for the validation_error
        :param value:
        :return:
        """
        # TODO: remove that when running in Python3
        if isinstance(value, six.string_types) and not isinstance(value, six.text_type):
            # the StringType accepts only unicode
            value = six.u(value)
        return self.type.cast(value)

    def validation_error(self, value):
        """
        Return an error message if the value is not valid according to the schema.
        It relies on exception thrown by the 'cast1 method of Type method.
        :param value:
        :return: None if value is valid or an error message string
        """
        error = None
        # override the integer validation. The default message is a bit cryptic if there's an error casting a string
        # like '1.2' into an int.
        if isinstance(self.type, types.IntegerType):
            if not is_blank_value(value):
                not_integer = False
                try:
                    casted = self.cast(value)
                    # there's also the case where the case where a float 1.2 is successfully casted in 1
                    # (ex: int(1.2) = 1)
                    if str(casted) != str(value):
                        not_integer = True
                except Exception:
                    not_integer = True
                if not_integer:
                    return 'The field "{}" must be a whole number.'.format(self.name)
        try:
            self.cast(value)
        except Exception as e:
            error = "{}".format(e)
            # Override the default enum exception message to include all possible values
            if error.find('enum array') and self.constraints.enum:
                values = [str(v) for v in self.constraints.enum]
                error = "The value must be one the following: {}".format(values)
        return error

    def __str__(self):
        return '{}'.format(self.name)


class SchemaConstraints:
    """
    A helper class for a schema field constraints
    """

    def __init__(self, data):
        self.data = data or {}

    # implement some dict like methods
    def __getitem__(self, item):
        return self.data.__getitem__(item)

    def get(self, k, d=None):
        return self.data.get(k, d)

    @property
    def required(self):
        return self.get('required', False)

    @property
    def enum(self):
        return self.get('enum')


@python_2_unicode_compatible
class SchemaForeignKey:
    """
    A utility class for foreign key in schema
    """

    def __init__(self, data):
        self.data = data

    def __str__(self):
        return 'Foreign Key {}'.format(self.data)

    # implement some dict like methods
    def __getitem__(self, item):
        return self.data.__getitem__(item)

    def get(self, k, d=None):
        return self.data.get(k, d)

    @staticmethod
    def _as_list(value):
        if isinstance(value, list):
            return value
        elif isinstance(value, six.string_types):
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


@python_2_unicode_compatible
class GenericSchema(object):
    """
    A utility class for schema.
    It uses internally an instance SchemaModel of the frictionless jsontableschema for help.
    https://github.com/frictionlessdata/jsontableschema-py#model
    Will throw an exception if the schema is not valid
    """

    def __init__(self, schema):
        self.data = schema
        self.schema_model = SchemaModel(schema)
        self.fields = [SchemaField(f) for f in self.schema_model.fields]
        self.foreign_keys = [SchemaForeignKey(fk) for fk in
                             self.schema_model.foreignKeys] if self.schema_model.foreignKeys else []

    # implement some dict like methods
    def __getitem__(self, item):
        return self.data.__getitem__(item)

    def get(self, k, d=None):
        return self.data.get(k, d)

    @property
    def headers(self):
        return self.field_names

    @property
    def field_names(self):
        return [f.name for f in self.fields]

    @property
    def required_fields(self):
        return [f for f in self.fields if f.required]

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
        The row must be a dictionary or a list of key => value
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

    def has_fk_for_model_field(self, model_name, model_field):
        return self.get_fk_for_model_field(model_name, model_field) is not None

    def get_fk_for_model_field(self, model_name, model_field):
        for fk in self.foreign_keys:
            if fk.model == model_name and fk.model_field == model_field:
                return fk
        return None

    def __str__(self):
        return self.get('name')


class ObservationSchema(GenericSchema):
    """
     A schema specific to an Observation Dataset.
     Its main job is to deal with the observation date and its geometry
     (lat/long or geojson)
     There's a special case: a lat/long or geometry field can be omitted if there's a reference (foreign key)
     to a site code (only)
    """
    OBSERVATION_DATE_FIELD_NAME = 'Observation Date'
    LATITUDE_FIELD_NAME = 'Latitude'
    LONGITUDE_FIELD_NAME = 'Longitude'
    EASTING_FIELD_NAME = 'Easting'
    NORTHING_FIELD_NAME = 'Northing'
    DATUM_FIELD_NAME = 'Datum'
    ZONE_FIELD_NAME = 'Zone'
    SITE_CODE_FIELD_NAME = 'Site Code'
    SITE_CODE_FOREIGN_KEY_EXAMPLE = """
        "foreignKeys": [
            {
                "fields": ["Site Code"],
                "reference": {
                    "fields": ["code"],
                    "resource": "Site"
                }
            }
        ]
     """

    def __init__(self, schema):
        super(ObservationSchema, self).__init__(schema)
        self.observation_date_field = self.find_observation_date_field_or_throw(self)
        self.geometry_parser = GeometryParser(self)
        if self.geometry_parser.errors:
            msg = "\n".join(self.geometry_parser.errors)
            raise ObservationSchemaError(msg)

    # The following method is static for testing purposes.
    @staticmethod
    def find_observation_date_field_or_throw(schema):
        """
        Precedence Rules:
        1- Look for a single date field with required = true
        2- Look for biosys.type = 'observationDate'
        3- Look for a field with name 'Observation Date' case insensitive
        4- If there's only one field of type date it's this one.
        5- Throw exception if not found
        :param schema: a dict descriptor or a Schema instance
        :return: The SchemaField or raise an exception if none or more than one
        """
        if not isinstance(schema, GenericSchema):
            schema = GenericSchema(schema)
        # edge case: a biosys observationDate set as not required
        if len([field for field in schema.fields
                if field.biosys.is_observation_date() and not field.required]) > 0:
            msg = "A biosys observationDate with required=false detected. It must be set required=true"
            raise ObservationSchemaError(msg)
        # normal cases
        required_date_fields = [field for field in schema.fields
                                if
                                (isinstance(field.type, types.DateType) or isinstance(field.type,
                                                                                      types.DateTimeType)) and
                                field.required
                                ]
        dates_count = len(required_date_fields)
        if dates_count == 0:
            msg = "One field must be of type 'date' with 'required': true to be a valid Observation schema."
            raise ObservationSchemaError(msg)
        if dates_count == 1:
            return required_date_fields[0]
        else:
            # more than one date fields. Look the the biosys type
            fields = [field for field in required_date_fields if field.biosys.is_observation_date()]
            count = len(fields)
            if count == 1:
                return fields[0]
            if count > 1:
                msg = "The schema contains more than one field tagged as a biosys type=observationDate"
                raise ObservationSchemaError(msg)
            # no biosys observation date. Look for field name
            fields = [field for field in required_date_fields if
                      field.name == ObservationSchema.OBSERVATION_DATE_FIELD_NAME]
            count = len(fields)
            if count == 1:
                return fields[0]
            if count > 1:
                msg = "The schema contains more than one field named Observation Date. " \
                      "One should be tagged as a biosys type=observationDate "
                raise ObservationSchemaError(msg)
            msg = "The schema doesn't include a required Observation Date field. " \
                  "It must have a field named {} or tagged with biosys type {}". \
                format(ObservationSchema.OBSERVATION_DATE_FIELD_NAME, BiosysSchema.OBSERVATION_DATE_TYPE_NAME)
            raise ObservationSchemaError(msg)

    @property
    def latitude_field(self):
        return self.geometry_parser.latitude_field

    @property
    def longitude_field(self):
        return self.geometry_parser.longitude_field

    @property
    def easting_field(self):
        return self.geometry_parser.easting_field

    @property
    def northing_field(self):
        return self.geometry_parser.northing_field

    @property
    def datum_field(self):
        return self.geometry_parser.datum_field

    @property
    def zone_field(self):
        return self.geometry_parser.zone_field

    @property
    def site_code_field(self):
        return self.geometry_parser.site_code_field

    def find_site_code_foreign(self):
        return self.get_fk_for_model_field('Site', 'code')

    def get_record_observation_date_value(self, record):
        return record.get(self.observation_date_field.name)

    def cast_record_observation_date(self, record):
        field = self.observation_date_field
        return field.cast(record.get(field.name))

    def cast_srid(self, record, default_srid=MODEL_SRID):
        return self.geometry_parser.cast_srid(record, default_srid=default_srid)

    def cast_geometry(self, record, default_srid=MODEL_SRID):
        return self.geometry_parser.cast_geometry(record, default_srid=default_srid)


class SpeciesObservationSchema(ObservationSchema):
    """
    An ObservationSchema with a Species Name
    """
    SPECIES_NAME_FIELD_NAME = 'Species Name'
    SPECIES_NAME_ID_FIELD_NAMES_LOWER = ['name id', 'nameid', 'species nameid', 'species name id']

    def __init__(self, schema):
        """
        An ObservationSchema with a field for species name or species nameid
        :param schema:
        """
        super(SpeciesObservationSchema, self).__init__(schema)
        try:
            self.species_name_field = self.find_species_name_field_or_throws(self, enforce_required=False)
        except SpeciesObservationSchemaError:
            self.species_name_field = None
        try:
            self.species_name_id_field = self.find_species_name_id_field(self)
        except SpeciesObservationSchemaError:
            self.species_name_field = None
        if not self.species_name_field and not self.species_name_id_field:
            msg = "The schema doesn't include a 'Species Name' field or a 'NameId' field. " \
                  "In order to be a valid Species Observation one of these fields must be specified. " \
                  "Alternatively you can 'tag' a field by adding a biosys type {} or {}" \
                .format(BiosysSchema.SPECIES_NAME_TYPE_NAME, BiosysSchema.SPECIES_NAME_ID_TYPE_NAME)
            raise SpeciesObservationSchemaError(msg)
        # if only one of the fields it must be required
        if self.species_name_field and not self.species_name_id_field and not self.species_name_field.required:
            msg = 'The {field_name} field must be set as "required" (add "required": true in the constraints)'.format(
                field_name=self.species_name_field.name
            )
            raise SpeciesObservationSchemaError(msg)
        if not self.species_name_field and self.species_name_id_field and not self.species_name_id_field.required:
            msg = 'The {field_name} field must be set as "required" (add "required": true in the constraints)'.format(
                field_name=self.species_name_id_field.name
            )
            raise SpeciesObservationSchemaError(msg)

    @staticmethod
    def find_species_name_field_or_throws(schema, enforce_required=True):
        """
        Precedence Rules:
        2- Look for biosys.type = 'speciesName'
        3- Look for a field with name 'Species Name' case insensitive
        :param schema: a dict descriptor or a Schema instance
        :return: The SchemaField or raise an exception if none or more than one
        """
        if not isinstance(schema, GenericSchema):
            schema = GenericSchema(schema)
        fields = [f for f in schema.fields if f.biosys.is_species_name()]
        if len(fields) > 1:
            msg = "More than one Biosys speciesName field found!. {}".format(fields)
            raise SpeciesObservationSchemaError(msg)
        if len(fields) == 1:
            field = fields[0]
            if enforce_required and not field.required:
                msg = "The Biosys speciesName field must be set as 'required'. {}".format(field)
                raise SpeciesObservationSchemaError(msg)
            else:
                return field
        # no Biosys species_name field found look for column name
        fields = [f for f in schema.fields if
                  f.name.lower() == SpeciesObservationSchema.SPECIES_NAME_FIELD_NAME.lower()]
        if len(fields) > 1:
            msg = "More than one 'Species Name' field found!. {}".format(fields)
            raise SpeciesObservationSchemaError(msg)
        if len(fields) == 1:
            field = fields[0]
            if enforce_required and not field.required:
                msg = "The 'Species Name' field must be set as 'required'. {}".format(field)
                raise SpeciesObservationSchemaError(msg)
            else:
                return field
        msg = "The schema doesn't include a required 'Species Name' field. " \
              "It must have a field named {} or tagged with biosys type {}". \
            format(SpeciesObservationSchema.SPECIES_NAME_FIELD_NAME, BiosysSchema.SPECIES_NAME_TYPE_NAME)
        raise SpeciesObservationSchemaError(msg)

    @staticmethod
    def find_species_name_id_field(schema):
        """
        Precedence Rules:
        2- Look for biosys.type = 'speciesNameId'
        3- Look for a field with name 'NameId' or one the the possible names, case insensitive
        Note:
            the method will raise an SpeciesObservationSchemaError if two or more fields match either of the two rules.
        """

        result = None
        if not isinstance(schema, GenericSchema):
            schema = GenericSchema(schema)
        fields = [f for f in schema.fields if f.biosys.is_species_name_id()]
        if len(fields) > 1:
            msg = "More than one Biosys {} type field found!. {}".format(BiosysSchema.SPECIES_NAME_ID_TYPE_NAME, fields)
            raise SpeciesObservationSchemaError(msg)
        if len(fields) == 1:
            result = fields[0]

        fields = [f for f in schema.fields if
                  f.name.lower() in SpeciesObservationSchema.SPECIES_NAME_ID_FIELD_NAMES_LOWER]
        if len(fields) > 1:
            msg = "More than one 'Species NameId' field found!. {}".format(fields)
            raise SpeciesObservationSchemaError(msg)
        if len(fields) == 1:
            result = fields[0]
        return result

    def cast_species_name(self, record):
        field = self.species_name_field
        return field.cast(record.get(field.name)) if field is not None else None

    def cast_species_name_id(self, record):
        field = self.species_name_id_field
        return field.cast(record.get(field.name)) if field is not None else None


def format_required_message(field):
    return "The field named '{field_name}' must have the 'required' constraint set to true.".format(
        field_name=field.name
    )


class GeometryParser(object):

    def __init__(self, schema):
        if not isinstance(schema, GenericSchema):
            schema = GenericSchema(schema)
        self.schema = schema
        self.errors = []

        # Site Code
        self.site_code_field, errors = self._find_site_code_field()
        if errors:
            self.errors += errors

        # Datum
        self.datum_field, errors = self._find_unique_field(
            BiosysSchema.DATUM_TYPE_NAME,
            ObservationSchema.DATUM_FIELD_NAME
        )
        if errors:
            self.errors += errors

        # Zone
        self.zone_field, errors = self._find_unique_field(
            BiosysSchema.ZONE_TYPE_NAME,
            ObservationSchema.ZONE_FIELD_NAME
        )
        if errors:
            self.errors += errors

        # Latitude
        self.latitude_field, errors = self._find_unique_field(
            BiosysSchema.LATITUDE_TYPE_NAME,
            ObservationSchema.LATITUDE_FIELD_NAME
        )
        if errors:
            self.errors += errors

        # Longitude
        self.longitude_field, errors = self._find_unique_field(
            BiosysSchema.LONGITUDE_TYPE_NAME,
            ObservationSchema.LONGITUDE_FIELD_NAME)
        if errors:
            self.errors += errors

        # Easting
        self.easting_field, errors = self._find_unique_field(
            BiosysSchema.EASTING_TYPE_NAME,
            ObservationSchema.EASTING_FIELD_NAME
        )
        if errors:
            self.errors += errors

        # Northing
        self.northing_field, errors = self._find_unique_field(
            BiosysSchema.NORTHING_TYPE_NAME,
            ObservationSchema.NORTHING_FIELD_NAME
        )
        if errors:
            self.errors += errors

        # some post validations.
        # we need at least one method to get the geometry.
        if not any([
            self.site_code_field,
            self.latitude_field,
            self.longitude_field,
            self.easting_field,
            self.northing_field
        ]):
            msg = "The schema must contain some geometry fields: latitude/longitude or easting/northing or " \
                  "alternatively a reference to the Site Code."
            self.errors.append(msg)
        # if we have a latitude we must have a longitude and vice-versa
        if not self.errors:
            if self.latitude_field and not self.longitude_field:
                self.errors.append("Missing Longitude field")
            if self.longitude_field and not self.latitude_field:
                self.errors.append("Missing Latitude field")
                # same for easting and northing
            if self.easting_field and not self.northing_field:
                self.errors.append("Missing Northing field")
            if self.northing_field and not self.easting_field:
                self.errors.append("Missing Easting field")

        # verify 'required' constraints: required constraints must be set if we are in 'single' mode.
        # e.g lat/long without site code or easting/northing
        if self.is_site_code_only and not self.site_code_field.required:
            self.errors.append(format_required_message(self.site_code_field))
        if self.is_lat_long_only:
            if not self.latitude_field.required:
                self.errors.append(format_required_message(self.latitude_field))
            if not self.longitude_field.required:
                self.errors.append(format_required_message(self.longitude_field))
        if self.is_easting_northing_only:
            if not self.easting_field.required:
                self.errors.append(format_required_message(self.easting_field))
            if not self.northing_field.required:
                self.errors.append(format_required_message(self.northing_field))

    def is_valid(self):
        return not self.errors

    @property
    def is_easting_northing(self):
        return self.easting_field is not None and self.northing_field is not None

    @property
    def is_easting_northing_only(self):
        return all([
            self.is_easting_northing,
            not self.is_site_code,
            not self.is_lat_long
        ])

    @property
    def is_lat_long(self):
        return self.latitude_field is not None and self.longitude_field is not None

    @property
    def is_lat_long_only(self):
        return all([
            self.is_lat_long,
            not self.is_easting_northing,
            not self.is_site_code,
        ])

    @property
    def is_site_code(self):
        return self.site_code_field is not None

    @property
    def is_site_code_only(self):
        return all([
            self.is_site_code,
            not self.is_easting_northing,
            not self.is_lat_long
        ])

    def cast_srid(self, record, default_srid=MODEL_SRID):
        """
        Two cases:
        Datum only or datum + zone
        :param record:
        :param default_srid:
        :return:
        """
        result = default_srid
        if self.datum_field:
            datum_val = record.get(self.datum_field.name)
            if not datum_val:
                return default_srid
            if self.zone_field:
                zone_val = record.get(self.zone_field.name)
                if not zone_val:
                    return default_srid
                try:
                    int(zone_val)
                except:
                    msg = "Invalid Zone '{}'. Should be an integer.".format(zone_val)
                    raise InvalidDatumError(msg)
                try:
                    result = get_australian_zone_srid(datum_val, zone_val)
                except Exception as e:
                    raise InvalidDatumError(e)
            else:
                if not is_supported_datum(datum_val):
                    msg = "Invalid Datum '{}'. Should be one of: {}".format(datum_val, SUPPORTED_DATUMS)
                    raise InvalidDatumError(msg)
                else:
                    result = get_datum_srid(datum_val)
        return result

    def cast_geometry(self, record, default_srid=MODEL_SRID):
        """
        Precedences rules:
        easting/northing > lat/long > site geometry
        :param record:
        :param default_srid:
        :return: Will throw an exception if anything went wrong
        """
        x, y = (None, None)  # x = longitude or easting, y = latitude or northing.
        geometry = None

        if self.is_easting_northing:
            x = record.get(self.easting_field.name)
            y = record.get(self.northing_field.name)
        if (not x or not y) and self.is_lat_long:
            x = record.get(self.longitude_field.name)
            y = record.get(self.latitude_field.name)
        if x and y:
            srid = self.cast_srid(record, default_srid=default_srid)
            geometry = Point(x=float(x), y=float(y), srid=srid)
        if geometry is None and self.site_code_field is not None:
            # extract geometry from site
            from main.models import Site  # import here to avoid cyclic import problem
            site_code = record.get(self.site_code_field.name)
            site = Site.objects.filter(code=site_code, geometry__isnull=False).first()
            geometry = site.geometry if site is not None else None
            if geometry is None and self.is_site_code_only:
                raise Exception('The site {} does not exist or has no geometry'.format(site_code))
        if geometry is not None:
            return geometry
        else:
            # problem
            raise Exception('No lat/long eating/northing or site code found!')

    def from_record_to_geometry(self, record, default_srid=MODEL_SRID):
        return self.cast_geometry(record, default_srid=default_srid)

    def from_geometry_to_record(self, geometry, record, default_srid=MODEL_SRID):
        if not geometry:
            return record
        # we can only deal with point. Getting the centroid should cover polygons
        point = geometry.centroid
        # convert the geometry in the record srid (if any)
        srid = self.cast_srid(record, default_srid=default_srid)
        if srid:
            point.transform(srid)
        # update record field
        record = record or {}
        if self.is_easting_northing and is_projected_srid(srid):
            if self.easting_field:
                record[self.easting_field.name] = point.x
            if self.northing_field:
                record[self.northing_field.name] = point.y
        elif self.is_lat_long and not is_projected_srid(srid):
            if self.longitude_field:
                record[self.longitude_field.name] = point.x
            if self.latitude_field:
                record[self.latitude_field.name] = point.y
        else:
            # what is going on here?
            # schema and datum/zone divergence?
            logger.warning("Ambiguous schema and coordinate system. "
                           "Cannot extract lat/long from a spherical coordinate system "
                           "or easting/northing from a projected one. "
                           "Schema: {}, srid: {}, record: {}".format(self.schema, srid, record))
        return record

    def _find_site_code_field(self):
        """
        The site code can be declared with a column named 'Site Code' or biosys type 'siteCode'
         but also with a foreign key (legacy)
        :return:
        """
        site_code_field, errors = self._find_unique_field(BiosysSchema.SITE_CODE_TYPE_NAME,
                                                          ObservationSchema.SITE_CODE_FIELD_NAME)
        if errors:
            return site_code_field, errors
        if site_code_field is None:
            site_code_fk = self.schema.get_fk_for_model_field('Site', 'code')
            site_code_field = self.schema.get_field_by_mame(site_code_fk.data_field) if site_code_fk else None
        return site_code_field, None

    def _find_unique_field(self, biosys_type, column_name):
        """
        Precedence Rules:
        1- Look for field with biosys.type = biosys_type
        2- Look for a field with name column_name case insensitive
        :return: (field, errors). field = None if not found. The only error is if the field is not unique.
        """
        fields = [f for f in self.schema.fields if f.biosys.type == biosys_type]
        if len(fields) > 1:
            msg = "More than one Biosys type {} field found: {}".format(biosys_type, [f.name for f in fields])
            return None, [msg]
        if len(fields) == 1:
            return fields[0], None
        # no Biosys type field found. Search for column name
        fields = [f for f in self.schema.fields if f.name.lower() == column_name.lower()]
        if len(fields) > 1:
            msg = "More than one field named {} found.".format(column_name)
            return None, [msg]
        if len(fields) == 1:
            return fields[0], None
        return None, None


class Exporter:
    def __init__(self, dataset, records=None):
        self.ds = dataset
        self.schema = GenericSchema(dataset.schema_data)
        self.headers = self.schema.headers
        self.warnings = []
        self.errors = []
        self.records = records if records else []

    def row_it(self):
        for record in self.records:
            row = []
            for field in self.schema.field_names:
                value = record.data.get(field, '')
                # TODO: remove that when running in Python3
                if isinstance(value, six.string_types) and not isinstance(value, six.text_type):
                    value = six.u(value)
                row.append(value)
            yield row

    def to_csv(self):
        rows = list()
        rows.append(self.headers)
        rows += list(self.row_it())
        return rows

    def _to_worksheet(self, ws):
        ws.title = self.ds.name
        # write headers
        headers = []
        for header in self.headers:
            cell = WriteOnlyCell(ws, value=header)
            cell.font = COLUMN_HEADER_FONT
            headers.append(cell)
        ws.append(headers)
        for row in self.row_it():
            ws.append(row)
        return ws

    def to_workbook(self):
        wb = Workbook(write_only=True)
        ws = wb.create_sheet()
        self._to_worksheet(ws)
        return wb
