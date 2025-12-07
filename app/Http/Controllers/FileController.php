<?php

namespace App\Http\Controllers;

use App\Actions\CompleteFileUploadAction;
use App\Actions\DeleteFileAction;
use App\Actions\RequestFileUploadAction;
use App\Http\Requests\CompleteFileUploadRequest;
use App\Http\Requests\DeleteFileRequest;
use App\Http\Requests\ListDatasetFilesRequest;
use App\Http\Requests\RequestFileUploadRequest;
use App\Models\Dataset;
use App\Models\File;
use App\Models\Organisation;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class FileController extends Controller
{
    /**
     * Request upload URLs for files.
     */
    public function requestUpload(
        RequestFileUploadRequest $request,
        Organisation $organisation, // Required for route model binding
        Dataset $dataset,
        RequestFileUploadAction $action
    ): JsonResponse {
        $uploadData = $action->execute(
            $request->validated('files'),
            $dataset,
            $request->user()
        );

        return response()->json([
            'upload_data' => $uploadData,
        ]);
    }

    /**
     * Complete file upload validation.
     */
    public function completeUpload(
        CompleteFileUploadRequest $request,
        Organisation $organisation, // Required for route model binding
        Dataset $dataset,
        CompleteFileUploadAction $action
    ): JsonResponse {
        $validatedFiles = $action->execute(
            $request->validated('file_ids'),
            $dataset
        );

        return response()->json([
            'files' => $validatedFiles,
        ]);
    }

    /**
     * List files for a dataset with pagination and search.
     */
    public function index(
        ListDatasetFilesRequest $request,
        Organisation $organisation, // Required for route model binding
        Dataset $dataset
    ): JsonResponse {
        $perPage = $request->validated('per_page', 15);
        $search = $request->validated('search');

        $query = $dataset->files()
            ->with('user')
            ->orderBy('created_at', 'desc');

        if ($search) {
            $query->where('original_filename', 'like', "%{$search}%");
        }

        $files = $query->paginate($perPage);

        return response()->json($files);
    }

    /**
     * Delete a file.
     */
    public function destroy(
        DeleteFileRequest $request,
        Organisation $organisation, // Required for route model binding
        Dataset $dataset,
        File $file,
        DeleteFileAction $action
    ): JsonResponse {
        $action->execute($file, $dataset);

        return response()->json([
            'message' => 'File deleted successfully.',
        ]);
    }
}
