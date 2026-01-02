<?php

namespace App\Http\Requests;

use App\Models\Audit;
use App\Models\Organisation;
use Illuminate\Foundation\Http\FormRequest;

class StartAuditRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        $organisation = $this->route('organisation');
        $audit = $this->route('audit');

        if (! $organisation instanceof Organisation || ! $audit instanceof Audit) {
            return false;
        }

        // Ensure audit belongs to organisation
        if ($audit->organisation_id !== $organisation->id) {
            return false;
        }

        // Ensure user is a member of the organisation
        if (! $this->user()->organisations()->where('organisations.id', $organisation->id)->exists()) {
            return false;
        }

        // Audit status must be pending
        return $audit->status === \App\Enums\AuditStatus::Pending;
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
