<?php

namespace App\Http\Controllers;

use App\Actions\CreateConversationAction;
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

        $conversation->load(['organisation', 'dataset', 'user', 'messages']);

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
        logger('sendMessage', [
            'request' => $request->validated(),
            'conversation' => $conversation,
        ]);
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
}
