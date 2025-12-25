<?php

namespace App\Http\Requests;

use App\Models\Organisation;
use App\Models\Research;
use Illuminate\Foundation\Http\FormRequest;

class StartResearchRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        $organisation = $this->route('organisation');
        $research = $this->route('research');

        if (! $organisation instanceof Organisation || ! $research instanceof Research) {
            return false;
        }

        // Ensure research belongs to organisation
        if ($research->organisation_id !== $organisation->id) {
            return false;
        }

        // Ensure user is a member of the organisation
        if (! $this->user()->organisations()->where('organisations.id', $organisation->id)->exists()) {
            return false;
        }

        // Research status must be pending
        return $research->status === 'pending';
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
