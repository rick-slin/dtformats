# -*- coding: utf-8 -*-
"""Apple Unified Logging and Activity Tracing files."""

import lz4.block

from dtformats import data_format
from dtformats import errors


class DSCRange(object):
  """Shared-Cache Strings (dsc) range.

  Attributes:
    path (str): path.
    range_offset (int): the offset of the range.
    range_sizes (int): the size of the range.
    uuid (uuid.UUID): the UUID.
    uuid_index (int): index of the UUID.
  """

  def __init__(self):
    """Initializes a Shared-Cache Strings (dsc) range."""
    super(DSCRange, self).__init__()
    self.path = None
    self.range_offset = None
    self.range_size = None
    self.uuid = None
    self.uuid_index = None


class DSCUUID(object):
  """Shared-Cache Strings (dsc) UUID.

  Attributes:
    path (str): path.
    sender_identifier (uuid.UUID): the sender identifier.
    text_offset (int): the offset of the text.
    text_sizes (int): the size of the text.
  """

  def __init__(self):
    """Initializes a Shared-Cache Strings (dsc) UUID."""
    super(DSCUUID, self).__init__()
    self.path = None
    self.sender_identifier = None
    self.text_offset = None
    self.text_size = None


class DSCFile(data_format.BinaryDataFile):
  """Shared-Cache Strings (dsc) file.

  Attributes:
    ranges (list[DSCRange]): the ranges.
    uuids (list[DSCUUID]): the UUIDs.
  """

  # Using a class constant significantly speeds up the time required to load
  # the dtFabric definition file.
  _FABRIC = data_format.BinaryDataFile.ReadDefinitionFile(
      'unified_logging.yaml')

  _DEBUG_INFO_FILE_HEADER = [
      ('signature', 'Signature', '_FormatStreamAsSignature'),
      ('major_format_version', 'Major format version',
       '_FormatIntegerAsDecimal'),
      ('minor_format_version', 'Minor format version',
       '_FormatIntegerAsDecimal'),
      ('number_of_ranges', 'Number of ranges', '_FormatIntegerAsDecimal'),
      ('number_of_uuids', 'Number of UUIDs', '_FormatIntegerAsDecimal')]

  _DEBUG_INFO_RANGE_DESCRIPTOR = [
      ('data_offset', 'Data offset', '_FormatIntegerAsHexadecimal8'),
      ('range_offset', 'Range offset', '_FormatIntegerAsHexadecimal8'),
      ('range_size', 'Range size', '_FormatIntegerAsDecimal'),
      ('unknown_offset', 'Unknown offset', '_FormatIntegerAsHexadecimal8'),
      ('uuid_descriptor_index', 'UUID descriptor index',
       '_FormatIntegerAsDecimal')]

  _DEBUG_INFO_UUID_DESCRIPTOR = [
      ('text_offset', 'Text offset', '_FormatIntegerAsHexadecimal8'),
      ('text_size', 'Text size', '_FormatIntegerAsDecimal'),
      ('sender_identifier', 'Sender identifier', '_FormatUUIDAsString'),
      ('path_offset', 'Path offset', '_FormatIntegerAsHexadecimal8')]

  def __init__(self, debug=False, output_writer=None):
    """Initializes a shared-cache strings (dsc) file.

    Args:
      debug (Optional[bool]): True if debug information should be written.
      output_writer (Optional[OutputWriter]): output writer.
    """
    super(DSCFile, self).__init__(debug=debug, output_writer=output_writer)
    self.ranges = []
    self.uuids = []

  def _FormatStreamAsSignature(self, stream):
    """Formats a stream as a signature.

    Args:
      stream (bytes): stream.

    Returns:
      str: stream formatted as a signature.
    """
    return stream.decode('ascii')

  def _ReadFileHeader(self, file_object):
    """Reads a file header.

    Args:
      file_object (file): file-like object.

    Returns:
      dsc_file_header: a file header.

    Raises:
      ParseError: if the file header cannot be read.
    """
    data_type_map = self._GetDataTypeMap('dsc_file_header')

    file_header, _ = self._ReadStructureFromFileObject(
        file_object, 0, data_type_map, 'file header')

    if self._debug:
      self._DebugPrintStructureObject(
          file_header, self._DEBUG_INFO_FILE_HEADER)

    if file_header.signature != b'hcsd':
      raise errors.ParseError('Unsupported signature.')

    format_version = (
        file_header.major_format_version, file_header.minor_format_version)
    if format_version not in [(1, 0), (2, 0)]:
      raise errors.ParseError(
          'Unsupported format version: {0:d}.{1:d}.'.format(
              file_header.major_format_version,
              file_header.minor_format_version))

    return file_header

  def _ReadRangeDescriptors(
      self, file_object, file_offset, version, number_of_ranges):
    """Reads the range descriptors.

    Args:
      file_object (file): file-like object.
      file_offset (int): offset of the start of range descriptors data relative
          to the start of the file.
      version (int): major version of the file.
      number_of_ranges (int): the number of range descriptions to retrieve.

    Yields:
      DSCRange: a range.

    Raises:
      ParseError: if the file cannot be read.
    """
    if version not in (1, 2):
      raise errors.ParseError('Unsupported format version: {0:d}.'.format(
          version))

    if version == 1:
      data_type_map_name = 'dsc_range_descriptor_v1'
      description = 'range descriptor v1'
    else:
      data_type_map_name = 'dsc_range_descriptor_v2'
      description = 'range descriptor v2'

    data_type_map = self._GetDataTypeMap(data_type_map_name)

    for _ in range(number_of_ranges):
      range_descriptor, record_size = self._ReadStructureFromFileObject(
          file_object, file_offset, data_type_map, description)

      file_offset += record_size

      if self._debug:
        self._DebugPrintStructureObject(
            range_descriptor, self._DEBUG_INFO_RANGE_DESCRIPTOR)

      dsc_range = DSCRange()
      dsc_range.range_offset = range_descriptor.range_offset
      dsc_range.range_size = range_descriptor.range_size
      dsc_range.uuid_index = range_descriptor.uuid_descriptor_index
      yield dsc_range

  def _ReadUUIDDescriptors(
      self, file_object, file_offset, version, number_of_uuids):
    """Reads the UUID descriptors.

    Args:
      file_object (file): file-like object.
      file_offset (int): offset of the start of UUID descriptors data relative
          to the start of the file.
      version (int): major version of the file
      number_of_uuids (int): the number of UUID descriptions to retrieve.

    Yields:
      DSCUUId: an UUID.

    Raises:
      ParseError: if the file cannot be read.
    """
    if version not in (1, 2):
      raise errors.ParseError('Unsupported format version: {0:d}.'.format(
          version))

    if version == 1:
      data_type_map_name = 'dsc_uuid_descriptor_v1'
      description = 'UUID descriptor v1'
    else:
      data_type_map_name = 'dsc_uuid_descriptor_v2'
      description = 'UUID descriptor v2'

    data_type_map = self._GetDataTypeMap(data_type_map_name)

    for _ in range(number_of_uuids):
      uuid_descriptor, record_size = self._ReadStructureFromFileObject(
          file_object, file_offset, data_type_map, description)

      file_offset += record_size

      if self._debug:
        self._DebugPrintStructureObject(
            uuid_descriptor, self._DEBUG_INFO_UUID_DESCRIPTOR)

      dsc_uuid = DSCUUID()
      dsc_uuid.sender_identifier = uuid_descriptor.sender_identifier
      dsc_uuid.text_offset = uuid_descriptor.text_offset
      dsc_uuid.text_size = uuid_descriptor.text_size

      dsc_uuid.path = self._ReadUUIDPath(
          file_object, uuid_descriptor.path_offset)

      yield dsc_uuid

  def _ReadUUIDPath(self, file_object, file_offset):
    """Reads an UUID path.

    Args:
      file_object (file): file-like object.
      file_offset (int): offset of the UUID path data relative to the start of
          the file.

    Returns:
      str: UUID path.

    Raises:
      ParseError: if the file cannot be read.
    """
    data_type_map = self._GetDataTypeMap('cstring')

    uuid_path, _ = self._ReadStructureFromFileObject(
        file_object, file_offset, data_type_map, 'UUID path')

    if self._debug:
      self._DebugPrintValue('UUID path', uuid_path)

    return uuid_path

  def ReadFileObject(self, file_object):
    """Reads a shared-cache strings (dsc) file-like object.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the file cannot be read.
    """
    file_header = self._ReadFileHeader(file_object)

    file_offset = file_object.tell()

    self.ranges = list(self._ReadRangeDescriptors(
        file_object, file_offset, file_header.major_format_version,
        file_header.number_of_ranges))

    file_offset = file_object.tell()

    self.uuids = list(self._ReadUUIDDescriptors(
        file_object, file_offset, file_header.major_format_version,
        file_header.number_of_uuids))

    for dsc_range in self.ranges:
      dsc_uuid = self.uuids[dsc_range.uuid_index]

      dsc_range.path = dsc_uuid.path
      dsc_range.uuid = dsc_uuid.sender_identifier


class TraceV3File(data_format.BinaryDataFile):
  """Apple Unified Logging and Activity Tracing (tracev3) file."""

  # Using a class constant significantly speeds up the time required to load
  # the dtFabric definition file.
  _FABRIC = data_format.BinaryDataFile.ReadDefinitionFile(
      'unified_logging.yaml')

  _CHUNK_TAG_FIREHOSE = 0x00006001

  _DEBUG_INFO_CATALOG = [
      ('sub_system_strings_offset', 'Sub system strings offset',
       '_FormatIntegerAsHexadecimal8'),
      ('process_information_entries_offset',
       'Process information entries offset', '_FormatIntegerAsHexadecimal8'),
      ('number_of_process_information_entries',
       'Number of process information entries', '_FormatIntegerAsDecimal'),
      ('sub_chunks_offset', 'Sub chunks offset',
       '_FormatIntegerAsHexadecimal8'),
      ('number_of_sub_chunks', 'Number of sub chunks',
       '_FormatIntegerAsDecimal'),
      ('unknown1', 'Unknown1', '_FormatIntegerAsHexadecimal8'),
      ('unknown2', 'Unknown2', '_FormatIntegerAsHexadecimal8'),
      ('unknown3', 'Unknown3', '_FormatIntegerAsHexadecimal8'),
      ('uuids', 'UUIDs', '_FormatArrayOfUUIDS'),
      ('sub_system_strings', 'Sub system strings', '_FormatArrayOfStrings')]

  _DEBUG_INFO_CHUNK_HEADER = [
      ('chunk_tag', 'Chunk tag', '_FormatIntegerAsHexadecimal8'),
      ('chunk_sub_tag', 'Chunk sub tag', '_FormatIntegerAsHexadecimal8'),
      ('chunk_data_size', 'Chunk data size', '_FormatIntegerAsDecimal'),
      ('unknown1', 'Unknown1', '_FormatIntegerAsHexadecimal8')]

  _DEBUG_INFO_FIREHOSE_HEADER = [
      ('unknown1', 'Unknown1', '_FormatIntegerAsHexadecimal8'),
      ('unknown2', 'Unknown2', '_FormatIntegerAsHexadecimal8'),
      ('unknown3', 'Unknown3', '_FormatIntegerAsHexadecimal8'),
      ('public_data_size', 'Public data size', '_FormatIntegerAsDecimal'),
      ('private_data_virtual_offset', 'Private data virtual offset',
       '_FormatIntegerAsHexadecimal4'),
      ('unknown4', 'Unknown4', '_FormatIntegerAsHexadecimal4'),
      ('unknown5', 'Unknown5', '_FormatIntegerAsHexadecimal4'),
      ('base_continous_time', 'Base continous time', '_FormatIntegerAsDecimal')]

  _DEBUG_INFO_FIREHOSE_TRACEPOINT = [
      ('unknown1', 'Unknown1', '_FormatIntegerAsHexadecimal2'),
      ('unknown2', 'Unknown2', '_FormatIntegerAsHexadecimal2'),
      ('unknown3', 'Unknown3', '_FormatIntegerAsHexadecimal4'),
      ('format_string_location', 'Format string location',
       '_FormatIntegerAsHexadecimal8'),
      ('thread_identifier', 'Thread identifier',
       '_FormatIntegerAsHexadecimal8'),
      ('continous_time_lower', 'Continous time (lower 32-bit)',
       '_FormatIntegerAsDecimal'),
      ('continous_time_upper', 'Continous time (upper 16-bit)',
       '_FormatIntegerAsDecimal'),
      ('data_size', 'Data size', '_FormatIntegerAsDecimal')]

  _DEBUG_INFO_LZ4_BLOCK_HEADER = [
      ('signature', 'Signature', '_FormatStreamAsSignature'),
      ('uncompressed_data_size', 'Uncompressed data size',
       '_FormatIntegerAsDecimal'),
      ('compressed_data_size', 'Compressed data size',
       '_FormatIntegerAsDecimal')]

  def __init__(self, debug=False, output_writer=None):
    """Initializes a timezone information file.

    Args:
      debug (Optional[bool]): True if debug information should be written.
      output_writer (Optional[OutputWriter]): output writer.
    """
    super(TraceV3File, self).__init__(
        debug=debug, output_writer=output_writer)

  def _FormatArrayOfStrings(self, array_of_strings):
    """Formats an array of strings.

    Args:
      array_of_strings (list[str]): array of strings.

    Returns:
      str: formatted array of strings.
    """
    return '{0:s}\n'.format('\n'.join([
        '\t[{0:03d}] {1:s}'.format(string_index, string)
        for string_index, string in enumerate(array_of_strings)]))

  def _FormatArrayOfUUIDS(self, array_of_uuids):
    """Formats an array of UUIDs.

    Args:
      array_of_uuids (list[uuid]): array of UUIDs.

    Returns:
      str: formatted array of UUIDs.
    """
    return '{0:s}\n'.format('\n'.join([
        '\t[{0:03d}] {1!s}'.format(uuid_index, uuid)
        for uuid_index, uuid in enumerate(array_of_uuids)]))

  def _FormatStreamAsSignature(self, stream):
    """Formats a stream as a signature.

    Args:
      stream (bytes): stream.

    Returns:
      str: stream formatted as a signature.
    """
    return stream.decode('ascii')

  def _ReadCatalog(self, file_object, file_offset, chunk_header):
    """Reads a catalog.

    Args:
      file_object (file): file-like object.
      file_offset (int): offset of the catalog data relative to the start
          of the file.
      chunk_header (tracev3_chunk_header): the chunk header of the catalog.

    Raises:
      ParseError: if the chunk header cannot be read.
    """
    chunk_data = file_object.read(chunk_header.chunk_data_size)

    # TODO: use chunk_data or remove
    _ = chunk_data

    data_type_map = self._GetDataTypeMap('tracev3_catalog')

    catalog, _ = self._ReadStructureFromFileObject(
        file_object, file_offset, data_type_map, 'Catalog')

    if self._debug:
      self._DebugPrintStructureObject(catalog, self._DEBUG_INFO_CATALOG)

  def _ReadChunkHeader(self, file_object, file_offset):
    """Reads a chunk header.

    Args:
      file_object (file): file-like object.
      file_offset (int): offset of the chunk header relative to the start
          of the file.

    Returns:
      tracev3_chunk_header: a chunk header.

    Raises:
      ParseError: if the chunk header cannot be read.
    """
    data_type_map = self._GetDataTypeMap('tracev3_chunk_header')

    chunk_header, _ = self._ReadStructureFromFileObject(
        file_object, file_offset, data_type_map, 'chunk header')

    if self._debug:
      self._DebugPrintStructureObject(
          chunk_header, self._DEBUG_INFO_CHUNK_HEADER)

    return chunk_header

  def _ReadChunkSet(self, file_object, file_offset, chunk_header):
    """Reads a chunk set.

    Args:
      file_object (file): file-like object.
      file_offset (int): offset of the chunk set data relative to the start
          of the file.
      chunk_header (tracev3_chunk_header): the chunk header of the chunk set.

    Raises:
      ParseError: if the chunk header cannot be read.
    """
    chunk_data = file_object.read(chunk_header.chunk_data_size)

    data_type_map = self._GetDataTypeMap('tracev3_lz4_block_header')

    lz4_block_header, _ = self._ReadStructureFromFileObject(
        file_object, file_offset, data_type_map, 'LZ4 block header')

    if self._debug:
      self._DebugPrintStructureObject(
          lz4_block_header, self._DEBUG_INFO_LZ4_BLOCK_HEADER)

    end_of_compressed_data_offset = 12 + lz4_block_header.compressed_data_size

    if lz4_block_header.signature == b'bv41':
      uncompressed_data = lz4.block.decompress(
          chunk_data[12:end_of_compressed_data_offset],
          uncompressed_size=lz4_block_header.uncompressed_data_size)

    elif lz4_block_header.signature == b'bv4-':
      uncompressed_data = chunk_data[12:end_of_compressed_data_offset]

    else:
      raise errors.ParseError('Unsupported start of compressed data marker')

    end_of_compressed_data_identifier = chunk_data[
        end_of_compressed_data_offset:end_of_compressed_data_offset + 4]

    if end_of_compressed_data_identifier != b'bv4$':
      raise errors.ParseError('Unsupported end of compressed data marker')

    data_type_map = self._GetDataTypeMap('tracev3_chunk_header')

    data_offset = 0
    while data_offset < lz4_block_header.uncompressed_data_size:
      if self._debug:
        self._DebugPrintData('Chunk header data', uncompressed_data[
            data_offset:data_offset + 16])

      chunkset_chunk_header = self._ReadStructureFromByteStream(
          uncompressed_data, data_offset, data_type_map, 'chunk header')
      data_offset += 16

      if self._debug:
        self._DebugPrintStructureObject(
            chunkset_chunk_header, self._DEBUG_INFO_CHUNK_HEADER)

      data_end_offset = data_offset + chunkset_chunk_header.chunk_data_size
      chunkset_chunk_data = uncompressed_data[data_offset:data_end_offset]
      if self._debug:
        self._DebugPrintData('Chunk data', chunkset_chunk_data)

      if chunkset_chunk_header.chunk_tag == self._CHUNK_TAG_FIREHOSE:
        self._ReadFirehoseChunkData(
            chunkset_chunk_data, chunkset_chunk_header.chunk_data_size,
            data_offset)

      data_offset = data_end_offset

      _, alignment = divmod(data_offset, 8)
      if alignment > 0:
        alignment = 8 - alignment

      data_offset += alignment

  def _ReadFirehoseChunkData(self, chunk_data, chunk_data_size, data_offset):
    """Reads firehose chunk data.

    Args:
      chunk_data (bytes): firehose chunk data.
      chunk_data_size (int): size of the firehose chunk data.
      data_offset (int): offset of the firehose chunk relative to the start
          of the chunk set.

    Raises:
      ParseError: if the firehose chunk cannot be read.
    """
    data_type_map = self._GetDataTypeMap('tracev3_firehose_header')

    firehose_header = self._ReadStructureFromByteStream(
        chunk_data, data_offset, data_type_map, 'firehose header')

    if self._debug:
      self._DebugPrintStructureObject(
          firehose_header, self._DEBUG_INFO_FIREHOSE_HEADER)

    chunk_data_offset = 32
    while chunk_data_offset < chunk_data_size:
      firehose_tracepoint = self._ReadFirehoseTracepointData(
          chunk_data[chunk_data_offset:], data_offset + chunk_data_offset)

      test_data_offset = chunk_data_offset + 22
      test_data_end_offset = test_data_offset + firehose_tracepoint.data_size
      self._DebugPrintData(
          'Data', chunk_data[test_data_offset:test_data_end_offset])

      chunk_data_offset += 22 + firehose_tracepoint.data_size

  def _ReadFirehoseTracepointData(self, tracepoint_data, data_offset):
    """Reads firehose tracepoint data.

    Args:
      tracepoint_data (bytes): firehose tracepoint data.
      data_offset (int): offset of the firehose tracepoint relative to
          the start of the chunk set.

    Returns:
      tracev3_firehose_tracepoint: a firehose tracepoint.

    Raises:
      ParseError: if the firehose tracepoint cannot be read.
    """
    data_type_map = self._GetDataTypeMap('tracev3_firehose_tracepoint')

    firehose_tracepoint = self._ReadStructureFromByteStream(
        tracepoint_data, data_offset, data_type_map, 'firehose tracepoint')

    if self._debug:
      self._DebugPrintStructureObject(
          firehose_tracepoint, self._DEBUG_INFO_FIREHOSE_TRACEPOINT)

    return firehose_tracepoint

  def ReadFileObject(self, file_object):
    """Reads a timezone information file-like object.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the file cannot be read.
    """
    file_offset = 0

    while file_offset < self._file_size:
      chunk_header = self._ReadChunkHeader(file_object, file_offset)
      file_offset += 16

      if chunk_header.chunk_tag == 0x600b:
        self._ReadCatalog(file_object, file_offset, chunk_header)

      elif chunk_header.chunk_tag == 0x600d:
        self._ReadChunkSet(file_object, file_offset, chunk_header)

      file_offset += chunk_header.chunk_data_size

      _, alignment = divmod(file_offset, 8)
      if alignment > 0:
        alignment = 8 - alignment

      file_offset += alignment


class UUIDTextFile(data_format.BinaryDataFile):
  """Apple Unified Logging and Activity Tracing (uuidtext) file."""

  # Using a class constant significantly speeds up the time required to load
  # the dtFabric definition file.
  _FABRIC = data_format.BinaryDataFile.ReadDefinitionFile(
      'unified_logging.yaml')

  _DEBUG_INFO_FILE_FOOTER = [
      ('library_path', 'Library path', '_FormatString')]

  _DEBUG_INFO_FILE_HEADER = [
      ('signature', 'Signature', '_FormatIntegerAsHexadecimal8'),
      ('major_format_version', 'Major format version',
       '_FormatIntegerAsDecimal'),
      ('minor_format_version', 'Minor format version',
       '_FormatIntegerAsDecimal'),
      ('number_of_entries', 'Number of entries', '_FormatIntegerAsDecimal'),
      ('entry_descriptors', 'Entry descriptors',
       '_FormatArrayOfEntryDescriptors')]

  def __init__(self, debug=False, output_writer=None):
    """Initializes a timezone information file.

    Args:
      debug (Optional[bool]): True if debug information should be written.
      output_writer (Optional[OutputWriter]): output writer.
    """
    super(UUIDTextFile, self).__init__(
        debug=debug, output_writer=output_writer)

  def _FormatArrayOfEntryDescriptors(self, array_of_entry_descriptors):
    """Formats an array of entry descriptors.

    Args:
      array_of_entry_descriptors (list[uuidtext_entry_descriptor]): array of
          entry descriptors.

    Returns:
      str: formatted array of entry descriptors.
    """
    return '{0:s}\n'.format('\n'.join([
        '\t[{0:03d}] offset: 0x{1:08x}, data size: {2:d}'.format(
            entry_index, entry_descriptor.offset, entry_descriptor.data_size)
        for entry_index, entry_descriptor in enumerate(
            array_of_entry_descriptors)]))

  def _ReadFileFooter(self, file_object, file_offset):
    """Reads a file footer.

    Args:
      file_object (file): file-like object.
      file_offset (int): offset of the file footer relative to the start
          of the file.

    Raises:
      ParseError: if the file footer cannot be read.
    """
    data_type_map = self._GetDataTypeMap('uuidtext_file_footer')

    file_footer, _ = self._ReadStructureFromFileObject(
        file_object, file_offset, data_type_map, 'file footer')

    if self._debug:
      self._DebugPrintStructureObject(
          file_footer, self._DEBUG_INFO_FILE_FOOTER)

  def _ReadFileHeader(self, file_object):
    """Reads a file header.

    Args:
      file_object (file): file-like object.

    Returns:
      uuidtext_file_header: a file header.

    Raises:
      ParseError: if the file header cannot be read.
    """
    data_type_map = self._GetDataTypeMap('uuidtext_file_header')

    file_header, _ = self._ReadStructureFromFileObject(
        file_object, 0, data_type_map, 'file header')

    if self._debug:
      self._DebugPrintStructureObject(
          file_header, self._DEBUG_INFO_FILE_HEADER)

    if file_header.signature != 0x66778899:
      raise errors.ParseError(
          'Unsupported signature: 0x{0:04x}.'.format(file_header.signature))

    format_version = (
        file_header.major_format_version, file_header.minor_format_version)
    if format_version != (2, 1):
      raise errors.ParseError(
          'Unsupported format version: {0:d}.{1:d}.'.format(
              file_header.major_format_version,
              file_header.minor_format_version))

    return file_header

  def ReadFileObject(self, file_object):
    """Reads a timezone information file-like object.

    Args:
      file_object (file): file-like object.

    Raises:
      ParseError: if the file cannot be read.
    """
    file_header = self._ReadFileHeader(file_object)

    file_offset = file_object.tell()
    for entry_descriptor in file_header.entry_descriptors:
      file_offset += entry_descriptor.data_size

    self._ReadFileFooter(file_object, file_offset)
