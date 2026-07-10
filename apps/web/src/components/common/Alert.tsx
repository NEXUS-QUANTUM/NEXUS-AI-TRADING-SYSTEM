import { Alert, AlertTitle, AlertDescription } from '@/components/common/Alert';

// Alert simple
<Alert variant="info">
  <AlertTitle>Information</AlertTitle>
  <AlertDescription>
    Ceci est un message d'information.
  </AlertDescription>
</Alert>

// Alert avec bouton de fermeture
<Alert variant="success" closable onClose={() => console.log('Fermé')}>
  <AlertTitle>Succès</AlertTitle>
  <AlertDescription>
    Opération effectuée avec succès.
  </AlertDescription>
</Alert>

// Alert avec actions
<AlertWithActions 
  variant="warning" 
  actions={
    <Button variant="outline" size="sm">Annuler</Button>
    <Button variant="default" size="sm">Confirmer</Button>
  }
>
  <AlertTitle>Attention</AlertTitle>
  <AlertDescription>
    Êtes-vous sûr de vouloir effectuer cette action ?
  </AlertDescription>
</AlertWithActions>
