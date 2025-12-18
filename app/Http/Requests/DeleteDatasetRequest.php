<?php

namespace App\Http\Requests;

use App\Models\Organisation;
use Illuminate\Foundation\Http\FormRequest;

class DeleteDatasetRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        $organisation = $this->route('organisation');

        if (! $organisation instanceof Organisation) {
            return false;
        }

        return $this->user()->isAdminOf($organisation);
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, \Illuminate\Contracts\Validation\ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        return [
            'delete_files' => ['sometimes', 'boolean'],
            'delete_conversations' => ['sometimes', 'boolean'],
        ];
    }

    /**
     * Prepare the data for validation.
     */
    protected function prepareForValidation(): void
    {
        $this->merge([
            'delete_files' => $this->boolean('delete_files', false),
            'delete_conversations' => $this->boolean('delete_conversations', false),
        ]);
    }
}
