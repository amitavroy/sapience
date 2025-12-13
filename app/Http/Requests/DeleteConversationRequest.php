<?php

namespace App\Http\Requests;

use App\Models\Conversation;
use App\Models\Organisation;
use Illuminate\Foundation\Http\FormRequest;

class DeleteConversationRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        $organisation = $this->route('organisation');
        $conversation = $this->route('conversation');

        if (! $organisation instanceof Organisation || ! $conversation instanceof Conversation) {
            return false;
        }

        // Ensure conversation belongs to organisation
        if ($conversation->organisation_id !== $organisation->id) {
            return false;
        }

        // User must be a member of the organisation
        if (! $this->user()->organisations()->where('organisations.id', $organisation->id)->exists()) {
            return false;
        }

        // User must be the conversation owner
        return $conversation->user_id === $this->user()->id;
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
