<?php

namespace App\Http\Controllers;

use App\Actions\CreateConversationAction;
use App\Actions\DeleteConversationAction;
use App\Http\Requests\DeleteConversationRequest;
use App\Http\Requests\SendMessageRequest;
use App\Models\Conversation;
use App\Models\Dataset;
use App\Models\Organisation;
use App\Neuron\SapienceBot;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;
use NeuronAI\Chat\Messages\UserMessage;

class ConversationController extends Controller
{
    /**
     * Display a listing of conversations for an organisation.
     */
    public function index(Request $request, Organisation $organisation): Response
    {
        $user = $request->user();

        // Ensure user belongs to this organisation
        if (! $user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            abort(403);
        }

        $conversations = Conversation::query()
            ->where('organisation_id', $organisation->id)
            ->with(['dataset', 'organisation', 'user'])
            ->orderBy('updated_at', 'desc')
            ->paginate(15);

        return Inertia::render('organisations/conversations/index', [
            'organisation' => $organisation,
            'conversations' => $conversations,
        ]);
    }

    /**
     * Store a newly created conversation.
     */
    public function store(Request $request, Organisation $organisation, Dataset $dataset, CreateConversationAction $action): RedirectResponse
    {
        $user = $request->user();

        // Ensure user belongs to this organisation
        if (! $user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            abort(403);
        }

        // Ensure dataset belongs to this organisation
        if ($dataset->organisation_id !== $organisation->id) {
            abort(404);
        }

        $conversation = $action->execute($organisation, $dataset, $user);

        return redirect()
            ->route('organisations.datasets.conversations.show', [$organisation, $dataset, $conversation]);
    }

    /**
     * Display the specified conversation.
     */
    public function show(Request $request, Organisation $organisation, Dataset $dataset, Conversation $conversation): Response
    {
        $user = $request->user();

        // Ensure user belongs to this organisation
        if (! $user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            abort(403);
        }

        // Ensure dataset belongs to this organisation
        if ($dataset->organisation_id !== $organisation->id) {
            abort(404);
        }

        // Ensure conversation belongs to this dataset
        if ($conversation->dataset_id !== $dataset->id) {
            abort(404);
        }

        // Ensure conversation belongs to this organisation
        if ($conversation->organisation_id !== $organisation->id) {
            abort(404);
        }

        $conversation->load([
            'organisation',
            'dataset',
            'user',
            'messages' => function ($query) {
                $query->orderBy('id', 'asc');
            },
        ]);

        return Inertia::render('organisations/datasets/conversations/show', [
            'organisation' => $organisation,
            'dataset' => $dataset,
            'conversation' => $conversation,
        ]);
    }

    /**
     * Send a message in a conversation.
     */
    public function sendMessage(SendMessageRequest $request, Conversation $conversation): JsonResponse
    {
        $organisationId = (int) $conversation->organisation_id;
        $datasetId = (int) $conversation->dataset_id;
        $threadId = $conversation->id;

        $response = (new SapienceBot(
            organisationId: $organisationId,
            datasetId: $datasetId,
            threadId: $threadId,
        ))->chat(new UserMessage($request->input('content')));

        return response()->json([
            'message' => [
                'content' => $response->getContent(),
                'role' => 'assistant',
            ],
        ]);
    }

    /**
     * Delete a conversation.
     */
    public function destroy(
        DeleteConversationRequest $request,
        Organisation $organisation,
        Conversation $conversation,
        DeleteConversationAction $action
    ): RedirectResponse {
        $action->execute($conversation);

        return redirect()
            ->route('organisations.conversations.index', [$organisation])
            ->with('success', 'Conversation deleted successfully.');
    }
}
