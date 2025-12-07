<?php

namespace App\Http\Requests;

use App\Models\Dataset;
use App\Models\File;
use App\Models\Organisation;
use Illuminate\Foundation\Http\FormRequest;

class DeleteFileRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        $organisation = $this->route('organisation');
        $dataset = $this->route('dataset');
        $file = $this->route('file');

        if (! $organisation instanceof Organisation || ! $dataset instanceof Dataset || ! $file instanceof File) {
            return false;
        }

        // Ensure dataset belongs to organisation
        if ($dataset->organisation_id !== $organisation->id) {
            return false;
        }

        // Ensure file belongs to dataset
        if (! $file->datasets()->where('datasets.id', $dataset->id)->exists()) {
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
        return [
            //
        ];
    }
}
