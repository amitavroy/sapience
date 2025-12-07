<?php

namespace App\Http\Requests;

use App\Models\Dataset;
use App\Models\Organisation;
use Illuminate\Foundation\Http\FormRequest;

class RequestFileUploadRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        $organisation = $this->route('organisation');
        $dataset = $this->route('dataset');

        if (! $organisation instanceof Organisation || ! $dataset instanceof Dataset) {
            return false;
        }

        // Ensure dataset belongs to organisation
        if ($dataset->organisation_id !== $organisation->id) {
            return false;
        }

        // User must be a member of the organisation
        return $this->user()->organisations()->where('organisations.id', $organisation->id)->exists();
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, \Illuminate\Contracts\Validation\ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        $maxFileSize = config('filesystems.max_file_size', 100 * 1024 * 1024); // Default 100MB
        $allowedMimeTypes = config('filesystems.allowed_mime_types', []);

        return [
            'files' => ['required', 'array', 'min:1', 'max:50'],
            'files.*.original_filename' => ['required', 'string', 'max:255'],
            'files.*.file_size' => ['required', 'integer', 'min:1', 'max:'.$maxFileSize],
            'files.*.mime_type' => ['required', 'string', 'max:255', 'in:'.implode(',', $allowedMimeTypes)],
        ];
    }
}
