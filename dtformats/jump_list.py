# -*- coding: utf-8 -*-
"""Windows Jump List files:
* .automaticDestinations-ms
* .customDestinations-ms
"""

import logging
import os

import pyfwsi
import pylnk
import pyolecf

from dtformats import data_format
from dtformats import data_range
from dtformats import errors


class LNKFileEntry(object):
  """Windows Shortcut (LNK) file entry.

  Attributes:
    data_size (int): size of the LNK file entry data.
    identifier (str): LNK file entry identifier.
  """

  def __init__(self, identifier):
    """Initializes the LNK file entry object.

    Args:
      identifier (str): LNK file entry identifier.
    """
    super(LNKFileEntry, self).__init__()
    self._lnk_file = pylnk.file()
    self.identifier = identifier
    self.data_size = 0

  def Close(self):
    """Closes the LNK file entry."""
    self._lnk_file.close()

  def GetShellItems(self):
    """Retrieves the shell items.

    Yields:
      pyfswi.item: shell item.
    """
    if self._lnk_file.link_target_identifier_data:  # pylint: disable=using-constant-test
      shell_item_list = pyfwsi.item_list()
      shell_item_list.copy_from_byte_stream(
          self._lnk_file.link_target_identifier_data)

      for shell_item in iter(shell_item_list.items):
        yield shell_item

  def Open(self, file_object):
    """Opens the LNK file entry.

    Args:
      file_object (file): file-like object that contains the LNK file
          entry data.
    """
    self._lnk_file.open_file_object(file_object)

    # We cannot trust the file size in the LNK data so we get the last offset
    # that was read instead. Because of DataRange the offset will be relative
    # to the start of the LNK data.
    self.data_size = file_object.get_offset()


class AutomaticDestinationsFile(data_format.BinaryDataFile):
  """Automatic Destinations Jump List (.automaticDestinations-ms) file.

  Attributes:
    entries (list[LNKFileEntry]): LNK file entries.
    recovered_entries (list[LNKFileEntry]): recovered LNK file entries.
  """

  # Using a class constant significantly speeds up the time required to load
  # the dtFabric definition file.
  _FABRIC = data_format.BinaryDataFile.ReadDefinitionFile('jump_list.yaml')

  # TODO: debug print pin status.
  _DEBUG_INFO_DEST_LIST_ENTRY = [
      ('unknown1', 'Unknown1', '_FormatIntegerAsHexadecimal8'),
      ('droid_volume_identifier', 'Droid volume identifier',
       '_FormatUUIDAsString'),
      ('droid_file_identifier', 'Droid file identifier', '_FormatUUIDAsString'),
      ('birth_droid_volume_identifier', 'Birth droid volume identifier',
       '_FormatUUIDAsString'),
      ('birth_droid_file_identifier', 'Birth droid file identifier',
       '_FormatUUIDAsString'),
      ('hostname', 'Hostname', '_FormatString'),
      ('entry_number', 'Entry number', '_FormatIntegerAsDecimal'),
      ('unknown2', 'Unknown2', '_FormatIntegerAsHexadecimal8'),
      ('unknown3', 'Unknown3', '_FormatFloatingPoint'),
      ('last_modification_time', 'Last modification time',
       '_FormatIntegerAsFiletime'),
      ('pin_status', 'Pin status', '_FormatIntegerAsDecimal'),
      ('unknown4', 'Unknown4', '_FormatIntegerAsDecimal'),
      ('unknown5', 'Unknown5', '_FormatIntegerAsHexadecimal8'),
      ('unknown6', 'Unknown6', '_FormatIntegerAsHexadecimal8'),
      ('unknown4', 'Unknown4', '_FormatIntegerAsPathSize'),
      ('path', 'Path', '_FormatString'),
      ('unknown7', 'Unknown7', '_FormatIntegerAsHexadecimal8')]

  _DEBUG_INFO_DEST_LIST_HEADER = [
      ('format_version', 'Format version', '_FormatIntegerAsDecimal'),
      ('number_of_entries', 'Number of entries', '_FormatIntegerAsDecimal'),
      ('number_of_pinned_entries', 'Number of pinned entries',
       '_FormatIntegerAsDecimal'),
      ('unknown1', 'Unknown1', '_FormatFloatingPoint'),
      ('last_entry_number', 'Last entry number', '_FormatIntegerAsDecimal'),
      ('unknown2', 'Unknown2', '_FormatIntegerAsHexadecimal8'),
      ('last_revision_number', 'Last revision number',
       '_FormatIntegerAsDecimal'),
      ('unknown3', 'Unknown3', '_FormatIntegerAsHexadecimal8')]

  def __init__(self, debug=False, output_writer=None):
    """Initializes an Automatic Destinations Jump List file.

    Args:
      debug (Optional[bool]): True if debug information should be written.
      output_writer (Optional[OutputWriter]): output writer.
    """
    super(AutomaticDestinationsFile, self).__init__(
        debug=debug, output_writer=output_writer)
    self._format_version = None
    self.entries = []
    self.recovered_entries = []

  def _FormatIntegerAsPathSize(self, integer):
    """Formats an integer as a path size.

    Args:
      integer (int): integer.

    Returns:
      str: integer formatted as path size.
    """
    return '{0:d} characters ({1:d} bytes)'.format(integer, integer * 2)

  def _ReadDestList(self, olecf_file):
    """Reads the DestList stream.

    Args:
      olecf_file (pyolecf.file): OLECF file.

    Raises:
      ParseError: if the DestList stream is missing.
    """
    olecf_item = olecf_file.root_item.get_sub_item_by_name('DestList')
    if not olecf_item:
      raise errors.ParseError('Missing DestList stream.')

    self._ReadDestListHeader(olecf_item)

    stream_offset = olecf_item.get_offset()
    stream_size = olecf_item.get_size()
    while stream_offset < stream_size:
      entry_size = self._ReadDestListEntry(olecf_item, stream_offset)
      stream_offset += entry_size

  def _ReadDestListEntry(self, olecf_item, stream_offset):
    """Reads a DestList stream entry.

    Args:
      olecf_item (pyolecf.item): OLECF item.
      stream_offset (int): stream offset of the entry.

    Returns:
      int: entry data size.

    Raises:
      ParseError: if the DestList stream entry cannot be read.
    """
    if self._format_version == 1:
      data_type_map = self._GetDataTypeMap('dest_list_entry_v1')
      description = 'dest list entry v1'

    elif self._format_version >= 3:
      data_type_map = self._GetDataTypeMap('dest_list_entry_v3')
      description = 'dest list entry v3'

    dest_list_entry, entry_data_size = self._ReadStructureFromFileObject(
        olecf_item, stream_offset, data_type_map, description)

    if self._debug:
      self._DebugPrintStructureObject(
          dest_list_entry, self._DEBUG_INFO_DEST_LIST_ENTRY)

    return entry_data_size

  def _ReadDestListHeader(self, olecf_item):
    """Reads the DestList stream header.

    Args:
      olecf_item (pyolecf.item): OLECF item.

    Raises:
      ParseError: if the DestList stream header cannot be read.
    """
    stream_offset = olecf_item.tell()
    data_type_map = self._GetDataTypeMap('dest_list_header')

    dest_list_header, _ = self._ReadStructureFromFileObject(
        olecf_item, stream_offset, data_type_map, 'dest list header')

    if self._debug:
      self._DebugPrintStructureObject(
          dest_list_header, self._DEBUG_INFO_DEST_LIST_HEADER)

    if dest_list_header.format_version not in (1, 3, 4):
      raise errors.ParseError('Unsupported format version: {0:d}'.format(
          dest_list_header.format_version))

    self._format_version = dest_list_header.format_version

  def _ReadLNKFile(self, olecf_item):
    """Reads a LNK file.

    Args:
      olecf_item (pyolecf.item): OLECF item.

    Returns:
      LNKFileEntry: a LNK file entry.

    Raises:
      ParseError: if the LNK file cannot be read.
    """
    if self._debug:
      text = 'Reading LNK file from stream: {0:s}'.format(olecf_item.name)
      self._DebugPrintText(text)

    lnk_file_entry = LNKFileEntry(olecf_item.name)

    try:
      lnk_file_entry.Open(olecf_item)
    except IOError as exception:
      raise errors.ParseError((
          'Unable to parse LNK file from stream: {0:s} '
          'with error: {1:s}').format(olecf_item.name, exception))

    if self._debug:
      self._DebugPrintText('\n')

    return lnk_file_entry

  def _ReadLNKFiles(self, olecf_file):
    """Reads the LNK files.

    Args:
      olecf_file (pyolecf.file): OLECF file.
    """
    for olecf_item in olecf_file.root_item.sub_items:
      if olecf_item.name == 'DestList':
        continue

      lnk_file_entry = self._ReadLNKFile(olecf_item)
      if lnk_file_entry:
        self.entries.append(lnk_file_entry)

  def ReadFileObject(self, file_object):
    """Reads an Automatic Destinations Jump List file-like object.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the file cannot be read.
    """
    olecf_file = pyolecf.file()
    olecf_file.open_file_object(file_object)

    try:
      self._ReadDestList(olecf_file)
      self._ReadLNKFiles(olecf_file)

    finally:
      olecf_file.close()


class CustomDestinationsFile(data_format.BinaryDataFile):
  """Custom Destinations Jump List (.customDestinations-ms) file.

  Attributes:
    entries (list[LNKFileEntry]): LNK file entries.
    recovered_entries (list[LNKFileEntry]): recovered LNK file entries.
  """

  # Using a class constant significantly speeds up the time required to load
  # the dtFabric definition file.
  _FABRIC = data_format.BinaryDataFile.ReadDefinitionFile('jump_list.yaml')

  _FILE_FOOTER_SIGNATURE = 0xbabffbab

  _LNK_GUID = (
      b'\x01\x14\x02\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00\x46')

  _DEBUG_INFO_FILE_FOOTER = [
      ('signature', 'Signature', '_FormatIntegerAsHexadecimal8')]

  _DEBUG_INFO_FILE_HEADER = [
      ('unknown1', 'Unknown1', '_FormatIntegerAsHexadecimal8'),
      ('unknown2', 'Unknown2', '_FormatIntegerAsHexadecimal8'),
      ('unknown3', 'Unknown3', '_FormatIntegerAsHexadecimal8'),
      ('header_values_type', 'Header value type', '_FormatIntegerAsDecimal')]

  def __init__(self, debug=False, output_writer=None):
    """Initializes a Custom Destinations Jump List file.

    Args:
      debug (Optional[bool]): True if debug information should be written.
      output_writer (Optional[OutputWriter]): output writer.
    """
    super(CustomDestinationsFile, self).__init__(
        debug=debug, output_writer=output_writer)
    self.entries = []
    self.recovered_entries = []

  def _ReadFileFooter(self, file_object):
    """Reads the file footer.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the file footer cannot be read.
    """
    file_offset = file_object.tell()
    data_type_map = self._GetDataTypeMap('custom_file_footer')

    file_footer, _ = self._ReadStructureFromFileObject(
        file_object, file_offset, data_type_map, 'file footer')

    if self._debug:
      self._DebugPrintStructureObject(file_footer, self._DEBUG_INFO_FILE_FOOTER)

    if file_footer.signature != self._FILE_FOOTER_SIGNATURE:
      raise errors.ParseError(
          'Invalid footer signature at offset: 0x{0:08x}.'.format(file_offset))

  def _ReadFileHeader(self, file_object):
    """Reads the file header.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the file header cannot be read.
    """
    data_type_map = self._GetDataTypeMap('custom_file_header')

    file_header, file_offset = self._ReadStructureFromFileObject(
        file_object, 0, data_type_map, 'file header')

    if self._debug:
      self._DebugPrintStructureObject(file_header, self._DEBUG_INFO_FILE_HEADER)

    if file_header.unknown1 != 2:
      raise errors.ParseError('Unsupported unknown1: {0:d}.'.format(
          file_header.unknown1))

    if file_header.header_values_type > 2:
      raise errors.ParseError('Unsupported header value type: {0:d}.'.format(
          file_header.header_values_type))

    if file_header.header_values_type == 0:
      data_type_map_name = 'custom_file_header_value_type_0'
    else:
      data_type_map_name = 'custom_file_header_value_type_1_or_2'

    data_type_map = self._GetDataTypeMap(data_type_map_name)

    file_header_value, _ = self._ReadStructureFromFileObject(
        file_object, file_offset, data_type_map, 'custom file header value')

    if self._debug:
      if file_header.header_values_type == 0:
        value_string = '{0:d}'.format(file_header_value.number_of_characters)
        self._DebugPrintValue('Number of characters', value_string)

        # TODO: print string.

      value_string = '{0:d}'.format(file_header_value.number_of_entries)
      self._DebugPrintValue('Number of entries', value_string)

      self._DebugPrintText('\n')

  def _ReadLNKFile(self, file_object):
    """Reads a LNK file.

    Args:
      file_object (file): file-like object.

    Returns:
      LNKFileEntry: a LNK file entry.

    Raises:
      ParseError: if the LNK file cannot be read.
    """
    file_offset = file_object.tell()
    if self._debug:
      self._DebugPrintText(
          'Reading LNK file at offset: 0x{0:08x}\n'.format(file_offset))

    identifier = '0x{0:08x}'.format(file_offset)
    lnk_file_entry = LNKFileEntry(identifier)

    try:
      lnk_file_entry.Open(file_object)
    except IOError as exception:
      raise errors.ParseError((
          'Unable to parse LNK file at offset: 0x{0:08x} '
          'with error: {1:s}').format(file_offset, exception))

    if self._debug:
      self._DebugPrintText('\n')

    return lnk_file_entry

  def _ReadLNKFiles(self, file_object):
    """Reads the LNK files.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the LNK files cannot be read.
    """
    file_offset = file_object.tell()
    remaining_file_size = self._file_size - file_offset
    data_type_map = self._GetDataTypeMap('custom_entry_header')

    # The Custom Destination file does not have a unique signature in
    # the file header that is why we use the first LNK class identifier (GUID)
    # as a signature.
    first_guid_checked = False
    while remaining_file_size > 4:
      try:
        entry_header, _ = self._ReadStructureFromFileObject(
            file_object, file_offset, data_type_map, 'entry header')

      except errors.ParseError as exception:
        error_message = (
            'Unable to parse file entry header at offset: 0x{0:08x} '
            'with error: {1:s}').format(file_offset, exception)

        if not first_guid_checked:
          raise errors.ParseError(error_message)

        logging.warning(error_message)
        break

      if entry_header.guid != self._LNK_GUID:
        error_message = 'Invalid entry header at offset: 0x{0:08x}.'.format(
            file_offset)

        if not first_guid_checked:
          raise errors.ParseError(error_message)

        file_object.seek(-16, os.SEEK_CUR)
        self._ReadFileFooter(file_object)

        file_object.seek(-4, os.SEEK_CUR)
        break

      first_guid_checked = True
      file_offset += 16
      remaining_file_size -= 16

      lnk_file_object = data_range.DataRange(
          file_object, data_offset=file_offset, data_size=remaining_file_size)

      lnk_file_entry = self._ReadLNKFile(lnk_file_object)
      if lnk_file_entry:
        self.entries.append(lnk_file_entry)

      file_offset += lnk_file_entry.data_size
      remaining_file_size -= lnk_file_entry.data_size

      file_object.seek(file_offset, os.SEEK_SET)

  def ReadFileObject(self, file_object):
    """Reads a Custom Destinations Jump List file-like object.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the file cannot be read.
    """
    self._ReadFileHeader(file_object)
    self._ReadLNKFiles(file_object)

    file_offset = file_object.tell()
    if file_offset < self._file_size - 4:
      # TODO: recover LNK files
      # * scan for LNK GUID and run _ReadLNKFiles on remaining data.
      if self._debug:
        self._DebugPrintText('Detected trailing data\n')
        self._DebugPrintText('\n')

    self._ReadFileFooter(file_object)
