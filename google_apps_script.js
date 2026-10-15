/**
 * Script opcional para atualizar a planilha online pública automaticamente.
 * 
 * Como instalar no Google Sheets:
 * 1. Na sua planilha, clique em: Extensões > Apps Script
 * 2. Cole este código substituindo o que estiver lá.
 * 3. Clique em 'Implantar' (Deploy) > 'Nova implantação' (New deployment).
 * 4. Tipo: 'App da Web' (Web app).
 * 5. Quem tem acesso: 'Qualquer pessoa' (Anyone).
 * 6. Copie a URL gerada e coloque em APPS_SCRIPT_WEBHOOK_URL no seu config.py ou .env.
 */

function doGet(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var values = sheet.getDataRange().getValues();
    return ContentService.createTextOutput(JSON.stringify(values)).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({result: "error", message: err.toString()})).setMimeType(ContentService.MimeType.JSON);
  }
}

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var targetCnpj = data.cnpj.replace(/\D/g, "");
    var status = data.status; // 'CADASTRADO' ou 'INDISPONIVEL'
    var errorMessage = data.error_message || "";
    
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var values = sheet.getDataRange().getValues();
    var headers = values[0];
    
    // Procura as colunas de CNPJ e Status
    var cnpjCol = -1;
    var statusCol = -1;
    var obsCol = -1;
    
    for (var j = 0; j < headers.length; j++) {
      var h = headers[j].toString().toLowerCase();
      if (h.indexOf("cnpj") !== -1) cnpjCol = j;
      if (h.indexOf("status") !== -1) statusCol = j;
      if (h.indexOf("obs") !== -1 || h.indexOf("erro") !== -1 || h.indexOf("motivo") !== -1) obsCol = j;
    }
    
    // Se a coluna de status não existir, cria na última coluna
    if (statusCol === -1) {
      statusCol = headers.length;
      sheet.getRange(1, statusCol + 1).setValue("Status");
    }
    
    // Procura a linha com o CNPJ correspondente
    for (var i = 1; i < values.length; i++) {
      var rowCnpj = values[i][cnpjCol].toString().replace(/\D/g, "");
      if (rowCnpj === targetCnpj) {
        sheet.getRange(i + 1, statusCol + 1).setValue(status);
        if (obsCol !== -1 && errorMessage) {
          sheet.getRange(i + 1, obsCol + 1).setValue(errorMessage);
        }
        break;
      }
    }
    
    return ContentService.createTextOutput(JSON.stringify({result: "success"})).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({result: "error", message: err.toString()})).setMimeType(ContentService.MimeType.JSON);
  }
}
