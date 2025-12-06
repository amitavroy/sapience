import InputError from '@/components/input-error';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import AuthLayout from '@/layouts/auth-layout';
import { select } from '@/routes/organisations';
import { Form, Head } from '@inertiajs/react';
import { useState } from 'react';

interface Organisation {
    id: number;
    uuid: string;
    name: string;
}

interface SelectProps {
    organisations: Organisation[];
}

export default function Select({ organisations }: SelectProps) {
    const [selectedOrganisationId, setSelectedOrganisationId] = useState<
        number | null
    >(null);

    return (
        <AuthLayout
            title="Select an organisation"
            description="Choose which organisation you'd like to use. You can switch between organisations at any time."
        >
            <Head title="Select Organisation" />
            <Form {...select.store.form()} className="flex flex-col gap-6">
                {({ processing, errors }) => (
                    <>
                        <div className="flex min-h-[60vh] items-center justify-center">
                            <div className="flex w-full max-w-md flex-col gap-4">
                                {organisations.map((organisation) => (
                                    <button
                                        key={organisation.id}
                                        type="button"
                                        onClick={() =>
                                            setSelectedOrganisationId(
                                                organisation.id,
                                            )
                                        }
                                        className={`w-full rounded-lg border p-4 text-left transition-colors ${
                                            selectedOrganisationId ===
                                            organisation.id
                                                ? 'border-primary bg-primary/5'
                                                : 'border-border hover:bg-accent'
                                        }`}
                                    >
                                        <div className="font-medium">
                                            {organisation.name}
                                        </div>
                                    </button>
                                ))}
                                <input
                                    type="hidden"
                                    name="organisation_id"
                                    value={selectedOrganisationId || ''}
                                />
                                <InputError message={errors.organisation_id} />
                            </div>
                        </div>
                        <Button
                            type="submit"
                            className="w-full"
                            size="lg"
                            disabled={processing || !selectedOrganisationId}
                        >
                            {processing && <Spinner />}
                            Continue
                        </Button>
                    </>
                )}
            </Form>
        </AuthLayout>
    );
}
