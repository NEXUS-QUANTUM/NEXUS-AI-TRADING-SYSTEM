import {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogConfirm,
} from '@/components/common/AlertDialog';
import { Button } from '@/components/common/Button';

// Utilisation simple
<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="destructive">Supprimer</Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Êtes-vous sûr ?</AlertDialogTitle>
      <AlertDialogDescription>
        Cette action est irréversible. Cela supprimera définitivement vos données.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Annuler</AlertDialogCancel>
      <AlertDialogAction onClick={handleDelete}>Supprimer</AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>

// Utilisation avec le composant confirm
<AlertDialogConfirm
  isOpen={isOpen}
  onClose={() => setIsOpen(false)}
  onConfirm={handleConfirm}
  title="Confirmation"
  description="Voulez-vous vraiment effectuer cette action ?"
  confirmLabel="Oui, confirmer"
  cancelLabel="Non, annuler"
  variant="warning"
  isLoading={isLoading}
/>
