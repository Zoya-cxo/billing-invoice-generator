import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Placeholder } from './pages/Placeholder';
import Login from './pages/Login';
import CustomerList from './pages/CustomerList';
import CustomerForm from './pages/CustomerForm';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/customers"
            element={
              <ProtectedRoute>
                <CustomerList />
              </ProtectedRoute>
            }
          />
          <Route
            path="/customers/new"
            element={
              <ProtectedRoute>
                <CustomerForm />
              </ProtectedRoute>
            }
          />
          <Route
            path="/customers/:id/edit"
            element={
              <ProtectedRoute>
                <CustomerForm />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Placeholder label="Dashboard" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/invoices"
            element={
              <ProtectedRoute>
                <Placeholder label="Invoice List" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/invoices/:id"
            element={
              <ProtectedRoute>
                <Placeholder label="Invoice Detail" />
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
