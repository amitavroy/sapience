import InputError from '@/components/input-error';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';
import AuthLayout from '@/layouts/auth-layout';
import { store } from '@/routes/organisations';
import { Head, Form } from '@inertiajs/react';

export default function Create() {
    return (
        <AuthLayout
            title="Create an organisation"
            description="Enter a name for your new organisation. You will be the admin of this organisation."
        >
            <Head title="Create Organisation" />
            <Form
                {...store.form()}
                className="flex flex-col gap-6"
            >
                {({ processing, errors }) => (
                    <>
                        <div className="grid gap-6">
                            <div className="grid gap-2">
                                <Label htmlFor="name">Organisation Name</Label>
                                <Input
                                    id="name"
                                    type="text"
                                    name="name"
                                    required
                                    autoFocus
                                    tabIndex={1}
                                    placeholder="Enter organisation name"
                                />
                                <InputError message={errors.name} />
                            </div>

                            <Button
                                type="submit"
                                className="mt-2 w-full"
                                tabIndex={2}
                                disabled={processing}
                            >
                                {processing && <Spinner />}
                                Create Organisation
                            </Button>
                        </div>
                    </>
                )}
            </Form>
        </AuthLayout>
    );
}

