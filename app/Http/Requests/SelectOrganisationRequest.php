<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class SelectOrganisationRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return true;
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, \Illuminate\Contracts\Validation\ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        $user = $this->user();

        return [
            'organisation_id' => [
                'required',
                'integer',
                Rule::exists('organisations', 'id')->where(function ($query) use ($user) {
                    return $query->whereIn('id', $user->organisations()->pluck('organisations.id'));
                }),
            ],
        ];
    }
}
