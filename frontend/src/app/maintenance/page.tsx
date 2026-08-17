export default function MaintenancePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 px-6 text-center">
      <h1 className="text-2xl font-semibold">Temporarily unavailable</h1>
      <p className="max-w-md text-muted-foreground">
        Expense Tracker is undergoing maintenance and is not accepting new activity right now.
        Please check back later.
      </p>
    </div>
  )
}
