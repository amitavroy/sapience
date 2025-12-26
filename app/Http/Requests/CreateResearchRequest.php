<?php

namespace App\Http\Requests;

use App\Models\Organisation;
use Illuminate\Foundation\Http\FormRequest;

class CreateResearchRequest extends FormRequest
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
            'query' => ['required', 'string'],
            'instructions' => ['nullable', 'string'],
        ];
    }
}
