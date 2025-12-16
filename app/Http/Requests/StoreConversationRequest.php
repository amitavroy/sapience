<?php

namespace App\Http\Requests;

use App\Models\Dataset;
use App\Models\Organisation;
use Illuminate\Foundation\Http\FormRequest;

class StoreConversationRequest extends FormRequest
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

        // Ensure user belongs to this organisation
        if (! $this->user()->organisations()->where('organisations.id', $organisation->id)->exists()) {
            return false;
        }

        // Ensure dataset belongs to this organisation
        if ($dataset->organisation_id !== $organisation->id) {
            return false;
        }

        return true;
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
