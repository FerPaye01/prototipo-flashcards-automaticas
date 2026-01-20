# Unified Content Processing Pipeline

## Overview

The unified content processing pipeline provides a single, consistent workflow for handling all input types in the flashcard automation system. This implementation addresses task 5.2 from the flashcards UI enhancement specification.

## Key Features

### 1. Single Processing Workflow
- **Unified Interface**: All input types (PDF annotations, PDF full text, direct text) are processed through the same pipeline
- **Consistent Error Handling**: Standardized error handling and recovery across all input methods
- **Progress Reporting**: Real-time progress updates for all processing stages

### 2. Content Routing
- **Automatic Mode Detection**: Routes content based on input method selection
- **Validation**: Input validation specific to each mode before processing
- **Extraction**: Uses appropriate content extraction method for each input type

### 3. Processing Stages
1. **Initialization**: Setup and validation
2. **Content Extraction**: Extract text from source (PDF or direct input)
3. **Text Segmentation**: Divide text into token-appropriate chunks
4. **Flashcard Generation**: Generate flashcards for each segment
5. **Anki Import**: Import generated flashcards to Anki

## Architecture

### Core Components

#### `UnifiedContentProcessor`
- Main processing engine
- Handles all processing stages
- Manages state and progress reporting
- Provides cancellation support

#### `ProcessingPipelineIntegration`
- Integration layer with existing GUI
- Backward compatibility with legacy interfaces
- Input validation and routing

#### `ProcessingState` & `ProcessingResult`
- Data structures for state management
- Consistent result format across all input types

### Integration Points

#### Main GUI Integration
```python
# Initialize in FlashcardsGUI.__init__()
self.processing_integration = ProcessingPipelineIntegration()

# Process content
result = self.processing_integration.process_with_progress_reporting(
    input_mode=current_mode,
    source=source,
    progress_callback=self._on_processing_progress
)
```

#### Progress Reporting
```python
def _on_processing_progress(self, state: ProcessingState):
    # Handle progress updates
    progress_percent = int(state.progress * 100)
    self._log(f"{state.stage.value}: {progress_percent}%")
```

## Error Handling

### Consistent Error Management
- **Validation Errors**: Input validation before processing starts
- **Processing Errors**: Graceful handling of processing failures
- **Recovery**: Clear error messages and suggested actions

### Error Types
- Input validation failures
- Content extraction errors
- Segmentation issues
- API failures (flashcard generation, Anki import)
- Network connectivity problems

## Usage Examples

### Direct Text Processing
```python
from unified_content_processor import ProcessingPipelineIntegration
from input_method_controller import InputMode

integration = ProcessingPipelineIntegration()

# Validate input
is_valid, error = integration.validate_input_for_mode(
    InputMode.DIRECT_TEXT, 
    text_content
)

if is_valid:
    # Process content
    result = integration.process_with_progress_reporting(
        InputMode.DIRECT_TEXT,
        text_content,
        progress_callback
    )
```

### PDF File Processing
```python
# Single file
result = integration.process_with_progress_reporting(
    InputMode.PDF_ANNOTATIONS,
    "document.pdf",
    progress_callback
)

# Multiple files
result = integration.process_with_progress_reporting(
    InputMode.PDF_FULLTEXT,
    ["doc1.pdf", "doc2.pdf"],
    progress_callback
)
```

## Benefits

### For Users
- **Consistent Experience**: Same workflow regardless of input method
- **Better Feedback**: Real-time progress updates and clear error messages
- **Reliability**: Improved error handling and recovery

### For Developers
- **Maintainability**: Single codebase for all processing logic
- **Extensibility**: Easy to add new input methods or processing steps
- **Testing**: Centralized logic is easier to test and debug

## Requirements Addressed

This implementation addresses the following requirements from the specification:

- **Requirement 1.4**: Single processing workflow for all input types
- **Requirement 1.5**: Consistent error handling across input methods
- **Content Routing**: Automatic routing based on input method selection
- **Error Recovery**: Graceful handling of processing failures

## Files Modified/Created

### New Files
- `unified_content_processor.py`: Main implementation
- `UNIFIED_PROCESSOR_README.md`: This documentation

### Modified Files
- `programa_proyecto_flashcards_automaticas.py`: Updated to use unified processor
  - Added `ProcessingPipelineIntegration` initialization
  - Updated `_on_start_process()` to use unified pipeline
  - Added unified processing methods
  - Updated queue processing for new result format

## Backward Compatibility

The implementation maintains backward compatibility with existing interfaces:

- Legacy processing methods are preserved but deprecated
- Existing GUI components continue to work
- Configuration options are respected
- File processing workflow remains familiar to users

## Future Enhancements

Potential improvements for future versions:

1. **Batch Processing**: Process multiple content sources simultaneously
2. **Caching**: Cache processed content to avoid reprocessing
3. **Templates**: Support for different flashcard templates
4. **Export Options**: Additional export formats beyond Anki
5. **Cloud Integration**: Support for cloud-based processing services