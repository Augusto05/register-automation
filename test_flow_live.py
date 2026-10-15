import time
import json
from inspect_live import run_js

def run_test():
    print("=" * 60)
    print("INICIANDO TESTE DO FLUXO COMPLETO COM DADOS FICTÍCIOS")
    print("=" * 60)

    # 1. Clicar no botão 'Novo Lead'
    js_click_novo = """
    (function() {
        const btn = Array.from(document.querySelectorAll("button")).find(b => (b.innerText || "").trim().includes("Novo Lead"));
        if (btn) {
            btn.click();
            return JSON.stringify({ success: true, message: "Botão 'Novo Lead' clicado" });
        }
        return JSON.stringify({ success: false, message: "Botão 'Novo Lead' não encontrado" });
    })()
    """
    res = json.loads(run_js(js_click_novo))
    print("Passo 1:", res["message"])
    if not res["success"]:
        return

    time.sleep(2)

    # 2. Preencher os campos no Modal
    test_data = {
        "razao_social": "ALPHA SERVICOS DIGITAIS LTDA",
        "first_name": "ALPHA",
        "last_name": "SERVICOS DIGITAIS LTDA",
        "cnpj": "11222333000181",
        "phone": "5511998877665",
        "email": "contato@alphaservicos.com.br"
    }

    print(f"Passo 2: Preenchendo campos com dados fictícios:")
    print(f"  - Razão Social: {test_data['razao_social']}")
    print(f"  - Primeiro Nome: {test_data['first_name']}")
    print(f"  - Sobrenome: {test_data['last_name']}")
    print(f"  - CNPJ: {test_data['cnpj']} (sem formatação)")
    print(f"  - Telefone: {test_data['phone']} (55 + 11 dígitos)")
    print(f"  - Email: {test_data['email']}")

    js_fill_fields = f"""
    (function() {{
        const modal = document.querySelector("section[role='dialog']");
        if (!modal) return {{ success: false, error: "Modal não encontrado" }};

        function setVal(selector, val) {{
            const el = modal.querySelector(selector);
            if (el) {{
                el.value = val;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }}
            return false;
        }}

        const results = {{
            firstName: setVal("input[name='firstName']", "{test_data['first_name']}"),
            lastName: setVal("input[name='lastName']", "{test_data['last_name']}"),
            razaoSocial: setVal("input[name='RazaoSocial__c']", "{test_data['razao_social']}"),
            cnpj: setVal("input[name='CNPJ__c']", "{test_data['cnpj']}"),
            phone: setVal("input[name='Phone']", "{test_data['phone']}"),
            email: setVal("input[name='Email']", "{test_data['email']}")
        }};

        return JSON.stringify({{ success: true, results }});
    }})()
    """
    fill_res = json.loads(run_js(js_fill_fields))
    print("Resultado do preenchimento:", fill_res["results"])

    time.sleep(1.5)

    # 3. Submeter formulário clicando em 'Confirmar'
    print("\nPasso 3: Clicando no botão 'Confirmar'...")
    js_click_confirm = """
    (function() {
        const modal = document.querySelector("section[role='dialog']");
        if (!modal) return JSON.stringify({ success: false, error: "Modal não encontrado" });
        
        const btn = Array.from(modal.querySelectorAll("button")).find(b => (b.innerText || "").trim() === "Confirmar");
        if (btn) {
            btn.click();
            return JSON.stringify({ success: true, message: "Botão 'Confirmar' clicado com sucesso" });
        }
        return JSON.stringify({ success: false, error: "Botão Confirmar não encontrado" });
    })()
    """
    confirm_res = json.loads(run_js(js_click_confirm))
    print("Status do clique:", confirm_res)

    print("\nPasso 4: Aguardando resposta do Salesforce (5 segundos)...")
    time.sleep(5)

    # 4. Verificar resultado (Modal fechou? Apareceu toast ou erro?)
    js_check_status = """
    (function() {
        const modal = document.querySelector("section[role='dialog']");
        const toasts = Array.from(document.querySelectorAll(".slds-notify_toast, div[role='alert'], .toastContainer")).map(t => t.innerText.trim()).filter(Boolean);
        const modalVisible = modal !== null && modal.offsetParent !== null;
        
        let errors = [];
        if (modal) {
            errors = Array.from(modal.querySelectorAll(".slds-has-error, .slds-form-element__help")).map(e => e.innerText.trim()).filter(Boolean);
        }

        return JSON.stringify({
            modalStillOpen: modalVisible,
            toasts: toasts,
            inlineErrors: errors
        });
    })()
    """
    status_res = json.loads(run_js(js_check_status))
    print("\n=== RESPOSTA DO SISTEMA ===")
    print("Modal ainda aberto:", status_res["modalStillOpen"])
    if status_res["toasts"]:
        print("Toasts / Alertas na tela:", status_res["toasts"])
    if status_res["inlineErrors"]:
        print("Erros nos campos:", status_res["inlineErrors"])

    if not status_res["modalStillOpen"] and not status_res["inlineErrors"]:
        print("\n✅ FLUXO COMPLETADO COM SUCESSO! Lead cadastrado com sucesso no Salesforce!")
    else:
        print("\n⚠️ O Salesforce retornou validação/alerta (comportamento previsto pelo robô):")
        if status_res["toasts"]:
            print("  Alerta:", status_res["toasts"])
        if status_res["inlineErrors"]:
            print("  Validação:", status_res["inlineErrors"])
        print("O robô trata isso automaticamente marcando como INDISPONÍVEL e fechando o modal para o próximo lead.")

        # Limpar fechando o modal
        js_cleanup = """
        (function() {
            const btn = document.querySelector("button[title='Cancelar e fechar']");
            if (btn) { btn.click(); return "Modal fechado"; }
            return "Botão fechar não encontrado";
        })()
        """
        print("Limpeza:", run_js(js_cleanup))

if __name__ == "__main__":
    run_test()
